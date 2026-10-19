"""FactoryRelease v2: one immutable executable curriculum authority.

The historical :class:`FactoryRelease` remains the byte-stable v1 compatibility
artifact while current callers migrate.  This module is the target release
contract: canonical curriculum, source bindings, execution profile, compiled
plan, provider/modality implementation identity and source-verified release
specimens are hashed together.  Runtime cutover is deliberately separate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json

from ..curriculum import AnswerFamily
from .adapters import SourceAdapterRegistry
from .answers import (
    AnswerModality, AnswerModalityRegistry, compile_answer_heads,
)
from .curriculum_definition import (
    CapabilitySourceBinding, CapabilitySpec, CurriculumDefinition, GradeSpec,
    SourceBindingSet, validate_curriculum_definition, validate_source_bindings,
)
from .execution import (
    CapabilityExecution, CapabilityProfile, CapabilityProjectionDigests,
    CurriculumDelta, CurriculumProfile, ExecutionPlan, GradeExecution,
    GradeProfile, PlanLineage, ProjectionDigests, SemanticGeometryChange,
    compile_execution_plan, diff_execution_plans,
)
from .generation import draw_execution_rows
from .model import SourceAdapter


SCHEMA = "bilqis.mlx.factory-release/v2"


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


def _require_sha256(value: str, code: str) -> str:
    if (not isinstance(value, str) or len(value) != 64 or
            any(char not in "0123456789abcdef" for char in value)):
        raise ValueError(code)
    return value


def _tuples(value):
    if isinstance(value, list):
        return tuple(_tuples(item) for item in value)
    if isinstance(value, dict):
        return {key: _tuples(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class AnswerHeadBinding:
    kind: str
    values: tuple[str, ...]
    semantic_identities: tuple[str, ...]
    token_ids: tuple[int, ...]
    modality_id: str
    implementation_sha256: str

    def __post_init__(self) -> None:
        if (not self.kind or not self.modality_id or not self.values or
                len(self.values) != len(self.semantic_identities) or
                len(self.values) != len(self.token_ids) or
                len(set(self.values)) != len(self.values) or
                len(set(self.semantic_identities)) != len(self.semantic_identities) or
                len(set(self.token_ids)) != len(self.token_ids) or
                any(type(item) is not int or item < 0 for item in self.token_ids)):
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_ANSWER_HEAD_INVALID")
        _require_sha256(
            self.implementation_sha256,
            "FACTORY_EXECUTABLE_RELEASE_ANSWER_HEAD_IMPLEMENTATION_INVALID")


@dataclass(frozen=True)
class CapabilityVerificationReceipt:
    capability_id: str
    verification_seed: int
    specimen_count: int
    specimen_ids_sha256: str
    specimen_content_sha256: str
    source_projection_sha256: str
    coverage_projection_sha256: str
    answer_schema_projection_sha256: str

    def __post_init__(self) -> None:
        if (not self.capability_id or type(self.verification_seed) is not int or
                type(self.specimen_count) is not int or self.specimen_count < 1):
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_VERIFICATION_INVALID")
        for value in (
                self.specimen_ids_sha256, self.specimen_content_sha256,
                self.source_projection_sha256, self.coverage_projection_sha256,
                self.answer_schema_projection_sha256):
            _require_sha256(
                value, "FACTORY_EXECUTABLE_RELEASE_VERIFICATION_DIGEST_INVALID")

    def digest(self) -> str:
        return _digest(asdict(self))


@dataclass(frozen=True)
class VerifiedAssessmentSeal:
    grade_id: str
    cumulative_scope: tuple[str, ...]
    assessment_blueprint_sha256: str
    capability_receipt_sha256s: tuple[str, ...]
    seal_sha256: str

    def __post_init__(self) -> None:
        if (not self.grade_id or not self.cumulative_scope or
                len(set(self.cumulative_scope)) != len(self.cumulative_scope) or
                len(self.cumulative_scope) != len(self.capability_receipt_sha256s)):
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_ASSESSMENT_SEAL_INVALID")
        _require_sha256(
            self.assessment_blueprint_sha256,
            "FACTORY_EXECUTABLE_RELEASE_ASSESSMENT_BLUEPRINT_INVALID")
        for value in self.capability_receipt_sha256s:
            _require_sha256(
                value, "FACTORY_EXECUTABLE_RELEASE_ASSESSMENT_RECEIPT_INVALID")
        _require_sha256(
            self.seal_sha256,
            "FACTORY_EXECUTABLE_RELEASE_ASSESSMENT_SEAL_DIGEST_INVALID")

    def expected_digest(self) -> str:
        return _digest({
            "schema": "bilqis.mlx.verified-assessment/v1",
            "grade_id": self.grade_id,
            "cumulative_scope": self.cumulative_scope,
            "assessment_blueprint_sha256": self.assessment_blueprint_sha256,
            "capability_receipt_sha256s": self.capability_receipt_sha256s,
        })


@dataclass(frozen=True)
class ExecutableVerificationReceipt:
    verification_seed: int
    execution_plan_sha256: str
    source_binding_sha256: str
    provider_descriptors_sha256: str
    answer_modalities_sha256: str
    semantic_catalog_sha256: str
    answer_heads_sha256: str
    capabilities: tuple[CapabilityVerificationReceipt, ...]
    assessments: tuple[VerifiedAssessmentSeal, ...]

    def __post_init__(self) -> None:
        if (type(self.verification_seed) is not int or
                not self.capabilities or not self.assessments):
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_VERIFICATION_INVALID")
        for value in (
                self.execution_plan_sha256, self.source_binding_sha256,
                self.provider_descriptors_sha256, self.answer_modalities_sha256,
                self.semantic_catalog_sha256, self.answer_heads_sha256):
            _require_sha256(
                value, "FACTORY_EXECUTABLE_RELEASE_VERIFICATION_DIGEST_INVALID")


@dataclass(frozen=True)
class ExecutableFactoryRelease:
    """Version-2 FactoryRelease; the complete executable authority artifact."""

    schema: str
    curriculum: CurriculumDefinition
    source_bindings: SourceBindingSet
    profile: CurriculumProfile
    execution_plan: ExecutionPlan
    semantic_catalog_sha256: str
    source_adapters: tuple[SourceAdapter, ...]
    answer_modalities: tuple[AnswerModality, ...]
    answer_heads: tuple[AnswerHeadBinding, ...]
    verification: ExecutableVerificationReceipt
    predecessor_release_sha256: str | None
    transition: CurriculumDelta | None
    release_sha256: str

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_SCHEMA_INVALID")
        if self.predecessor_release_sha256 is not None:
            _require_sha256(
                self.predecessor_release_sha256,
                "FACTORY_EXECUTABLE_RELEASE_PREDECESSOR_INVALID")
        _require_sha256(
            self.semantic_catalog_sha256,
            "FACTORY_EXECUTABLE_RELEASE_CATALOG_INVALID")
        _require_sha256(
            self.release_sha256, "FACTORY_EXECUTABLE_RELEASE_DIGEST_INVALID")

    def manifest(self) -> dict:
        return {
            "schema": self.schema,
            "curriculum": asdict(self.curriculum),
            "source_bindings": asdict(self.source_bindings),
            "profile": asdict(self.profile),
            "execution_plan": asdict(self.execution_plan),
            "semantic_catalog_sha256": self.semantic_catalog_sha256,
            "source_adapters": [asdict(item) for item in self.source_adapters],
            "answer_modalities": [asdict(item) for item in self.answer_modalities],
            "answer_heads": [asdict(item) for item in self.answer_heads],
            "verification": asdict(self.verification),
            "predecessor_release_sha256": self.predecessor_release_sha256,
            "transition": (
                None if self.transition is None else asdict(self.transition)),
        }

    def expected_digest(self) -> str:
        return _digest(self.manifest())

    def verify(self) -> None:
        if self.release_sha256 != self.expected_digest():
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_CONTENT_DRIFT")

        answer_kinds = tuple(item.kind for item in self.answer_modalities)
        if len(set(answer_kinds)) != len(answer_kinds):
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_MODALITY_DRIFT")
        validate_curriculum_definition(
            self.curriculum, answer_kinds=answer_kinds)
        validate_source_bindings(self.curriculum, self.source_bindings)

        if self.profile.profile_id != self.execution_plan.profile_id:
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_PROFILE_DRIFT")
        if (self.curriculum.digest() != self.execution_plan.curriculum_sha256 or
                self.source_bindings.digest() !=
                self.execution_plan.source_binding_sha256):
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_PLAN_BINDING_DRIFT")

        providers = {item.adapter_id: item for item in self.source_adapters}
        if len(providers) != len(self.source_adapters):
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_PROVIDER_DRIFT")
        bindings = self.source_bindings.by_capability
        for execution in self.execution_plan.capabilities:
            provider = providers.get(execution.provider_id)
            binding = bindings.get(execution.capability_id)
            if (provider is None or binding is None or
                    execution.provider_implementation_sha256 !=
                    provider.implementation_sha256 or
                    binding.source_anchor != execution.source_anchor or
                    binding.generator_id != provider.generator_id or
                    execution.oracle_id != binding.oracle_id or
                    binding.oracle_id not in provider.accepted_oracle_ids):
                raise ValueError("FACTORY_EXECUTABLE_RELEASE_PROVIDER_DRIFT")
            provider.validate_profile_parameters(execution.provider_parameters)

        used_kinds = tuple(dict.fromkeys(
            family.kind for capability in self.execution_plan.capabilities
            for family in capability.answer_families))
        if used_kinds != answer_kinds:
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_MODALITY_DRIFT")
        modalities = {item.kind: item for item in self.answer_modalities}
        heads = {item.kind: item for item in self.answer_heads}
        if tuple(heads) != answer_kinds:
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_ANSWER_HEAD_DRIFT")
        for kind, head in heads.items():
            descriptor = modalities[kind]
            if (head.modality_id != descriptor.adapter_id or
                    head.implementation_sha256 != descriptor.implementation_sha256):
                raise ValueError("FACTORY_EXECUTABLE_RELEASE_ANSWER_HEAD_DRIFT")

        verification = self.verification
        if verification.semantic_catalog_sha256 != self.semantic_catalog_sha256:
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_CATALOG_DRIFT")
        if (verification.execution_plan_sha256 != self.execution_plan.digest() or
                verification.source_binding_sha256 != self.source_bindings.digest() or
                verification.provider_descriptors_sha256 !=
                _digest([asdict(item) for item in self.source_adapters]) or
                verification.answer_modalities_sha256 !=
                _digest([asdict(item) for item in self.answer_modalities]) or
                verification.answer_heads_sha256 !=
                _digest([asdict(item) for item in self.answer_heads])):
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_VERIFICATION_DRIFT")

        capability_ids = tuple(
            item.capability_id for item in self.execution_plan.capabilities)
        receipts = verification.capabilities
        if tuple(item.capability_id for item in receipts) != capability_ids:
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_VERIFICATION_DRIFT")
        projection_map = {
            item.capability_id: item
            for item in self.execution_plan.capability_projection_digests}
        execution_map = self.execution_plan.capability_map
        for receipt in receipts:
            execution = execution_map[receipt.capability_id]
            projection = projection_map[receipt.capability_id]
            if (receipt.verification_seed != verification.verification_seed or
                    receipt.specimen_count != execution.exam_item_count or
                    receipt.source_projection_sha256 != projection.source or
                    receipt.coverage_projection_sha256 != projection.coverage or
                    receipt.answer_schema_projection_sha256 !=
                    projection.answer_schema):
                raise ValueError("FACTORY_EXECUTABLE_RELEASE_VERIFICATION_DRIFT")

        receipt_map = {item.capability_id: item for item in receipts}
        if tuple(item.grade_id for item in verification.assessments) != tuple(
                item.grade_id for item in self.execution_plan.grades):
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_ASSESSMENT_DRIFT")
        for seal, grade in zip(
                verification.assessments, self.execution_plan.grades):
            expected_receipts = tuple(
                receipt_map[capability].digest()
                for capability in grade.cumulative_scope)
            if (seal.cumulative_scope != grade.cumulative_scope or
                    seal.assessment_blueprint_sha256 !=
                    grade.assessment_blueprint_sha256 or
                    seal.capability_receipt_sha256s != expected_receipts or
                    seal.seal_sha256 != seal.expected_digest()):
                raise ValueError("FACTORY_EXECUTABLE_RELEASE_ASSESSMENT_DRIFT")

        if self.predecessor_release_sha256 is None:
            if self.transition is not None:
                raise ValueError("FACTORY_EXECUTABLE_RELEASE_LINEAGE_DRIFT")
        else:
            if (self.transition is None or
                    self.transition.next_plan_sha256 !=
                    self.execution_plan.digest() or
                    self.transition.next_curriculum_sha256 !=
                    self.execution_plan.curriculum_sha256 or
                    self.transition.next_source_binding_sha256 !=
                    self.execution_plan.source_binding_sha256 or
                    self.transition.semantic_geometry ==
                    SemanticGeometryChange.INCOMPATIBLE.value):
                raise ValueError("FACTORY_EXECUTABLE_RELEASE_LINEAGE_DRIFT")

    def verify_semantic_catalog(self, graph: dict) -> None:
        """Bind the offline release artifact to the exact loaded semantic ABI."""
        names = graph.get("tokens") if isinstance(graph, dict) else None
        if (not isinstance(names, list) or not names or
                len(set(names)) != len(names) or
                any(not isinstance(name, str) or not name for name in names)):
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_CATALOG_INVALID")
        if _digest(tuple(names)) != self.semantic_catalog_sha256:
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_CATALOG_DRIFT")
        for head in self.answer_heads:
            if any(
                    token_id >= len(names) or
                    names[token_id] != identity
                    for identity, token_id in zip(
                        head.semantic_identities, head.token_ids)):
                raise ValueError(
                    "FACTORY_EXECUTABLE_RELEASE_ANSWER_HEAD_CATALOG_DRIFT")

    @classmethod
    def from_manifest(
            cls, payload: dict, release_sha256: str) -> "ExecutableFactoryRelease":
        """Decode v2 data without importing provider implementations."""
        try:
            curriculum = _decode_curriculum(payload["curriculum"])
            bindings = _decode_source_bindings(payload["source_bindings"])
            profile = _decode_profile(payload["profile"])
            plan = _decode_plan(payload["execution_plan"])
            verification = _decode_verification(payload["verification"])
            transition = (
                None if payload["transition"] is None
                else CurriculumDelta(**_tuples(payload["transition"])))
            release = cls(
                schema=payload["schema"],
                curriculum=curriculum,
                source_bindings=bindings,
                profile=profile,
                execution_plan=plan,
                semantic_catalog_sha256=payload["semantic_catalog_sha256"],
                source_adapters=tuple(
                    SourceAdapter(**_tuples(item))
                    for item in payload["source_adapters"]),
                answer_modalities=tuple(
                    AnswerModality(**item) for item in payload["answer_modalities"]),
                answer_heads=tuple(
                    AnswerHeadBinding(**_tuples(item))
                    for item in payload["answer_heads"]),
                verification=verification,
                predecessor_release_sha256=payload["predecessor_release_sha256"],
                transition=transition,
                release_sha256=release_sha256,
            )
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_MANIFEST_INVALID") from exc
        if _digest(payload) != release_sha256:
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_MANIFEST_CONTENT_DRIFT")
        release.verify()
        return release


def _decode_curriculum(value: dict) -> CurriculumDefinition:
    grades = []
    for grade in value["grades"]:
        capabilities = tuple(CapabilitySpec(
            **{
                **_tuples(capability),
                "answer_families": tuple(
                    AnswerFamily(**_tuples(family))
                    for family in capability["answer_families"]),
            })
            for capability in grade["capabilities"])
        grades.append(GradeSpec(
            **{
                **_tuples(grade),
                "capabilities": capabilities,
            }))
    return CurriculumDefinition(
        value["curriculum_id"], tuple(grades), value["program_complete"])


def _decode_source_bindings(value: dict) -> SourceBindingSet:
    return SourceBindingSet(
        tuple(CapabilitySourceBinding(**item) for item in value["bindings"]),
        value.get("source_attestation_sha256"))


def _decode_profile(value: dict) -> CurriculumProfile:
    return CurriculumProfile(
        value["profile_id"],
        tuple(GradeProfile(
            grade["grade_id"],
            None if grade["enabled_capabilities"] is None
            else tuple(grade["enabled_capabilities"]),
            tuple(CapabilityProfile(
                capability["capability_id"],
                _tuples(capability["provider_parameters"]),
                _tuples(capability["answer_family_values"]),
            ) for capability in grade["capabilities"]),
        ) for grade in value["grades"]))


def _decode_plan(value: dict) -> ExecutionPlan:
    capabilities = tuple(CapabilityExecution(
        **{
            **_tuples(item),
            "answer_families": tuple(
                AnswerFamily(**_tuples(family))
                for family in item["answer_families"]),
        })
        for item in value["capabilities"])
    return ExecutionPlan(
        profile_id=value["profile_id"],
        curriculum_sha256=value["curriculum_sha256"],
        source_binding_sha256=value["source_binding_sha256"],
        grades=tuple(GradeExecution(**_tuples(item)) for item in value["grades"]),
        capabilities=capabilities,
        projection_digests=ProjectionDigests(**value["projection_digests"]),
        capability_projection_digests=tuple(
            CapabilityProjectionDigests(**item)
            for item in value["capability_projection_digests"]),
    )


def _decode_verification(value: dict) -> ExecutableVerificationReceipt:
    return ExecutableVerificationReceipt(
        verification_seed=value["verification_seed"],
        execution_plan_sha256=value["execution_plan_sha256"],
        source_binding_sha256=value["source_binding_sha256"],
        provider_descriptors_sha256=value["provider_descriptors_sha256"],
        answer_modalities_sha256=value["answer_modalities_sha256"],
        semantic_catalog_sha256=value["semantic_catalog_sha256"],
        answer_heads_sha256=value["answer_heads_sha256"],
        capabilities=tuple(
            CapabilityVerificationReceipt(**item)
            for item in value["capabilities"]),
        assessments=tuple(
            VerifiedAssessmentSeal(**_tuples(item))
            for item in value["assessments"]),
    )


def _provider_descriptors(
        plan: ExecutionPlan, bindings: SourceBindingSet,
        registry: SourceAdapterRegistry) -> tuple[SourceAdapter, ...]:
    result = []
    seen = set()
    by_capability = bindings.by_capability
    for execution in plan.capabilities:
        binding = by_capability[execution.capability_id]
        descriptor = registry.require(
            binding.generator_id, binding.oracle_id).descriptor
        if descriptor.adapter_id not in seen:
            seen.add(descriptor.adapter_id)
            result.append(descriptor)
    return tuple(result)


def _answer_head_bindings(
        plan: ExecutionPlan, graph: dict,
        registry: AnswerModalityRegistry) -> tuple[AnswerHeadBinding, ...]:
    compiled = compile_answer_heads(plan, graph, registry)
    result = []
    for descriptor in registry.descriptors_for(plan):
        head = compiled[descriptor.kind]
        modality = registry.require(descriptor.kind)
        values = tuple(head["values"])
        result.append(AnswerHeadBinding(
            kind=descriptor.kind,
            values=values,
            semantic_identities=tuple(
                modality.resolve_identity(value) for value in values),
            token_ids=tuple(head["token_ids"]),
            modality_id=descriptor.adapter_id,
            implementation_sha256=descriptor.implementation_sha256,
        ))
    return tuple(result)


def _verification_receipt(
        curriculum: CurriculumDefinition, bindings: SourceBindingSet,
        plan: ExecutionPlan, source_registry: SourceAdapterRegistry,
        answer_modalities: tuple[AnswerModality, ...],
        answer_heads: tuple[AnswerHeadBinding, ...], *, source_root, graph: dict,
        verification_seed: int, legacy_course=None) -> ExecutableVerificationReceipt:
    projection_map = {
        item.capability_id: item for item in plan.capability_projection_digests}
    receipts = []
    for execution in plan.capabilities:
        rows = draw_execution_rows(
            source_root, graph, curriculum, plan, source_registry,
            source_bindings=bindings, legacy_course=legacy_course,
            seed=verification_seed, capability=execution.capability_id,
            each=execution.exam_item_count)
        row_ids = tuple(row["id"] for row in rows)
        if len(set(row_ids)) != len(row_ids):
            raise ValueError(
                "FACTORY_EXECUTABLE_RELEASE_DUPLICATE_SPECIMEN:"
                + execution.capability_id)
        projection = projection_map[execution.capability_id]
        receipts.append(CapabilityVerificationReceipt(
            capability_id=execution.capability_id,
            verification_seed=verification_seed,
            specimen_count=len(rows),
            specimen_ids_sha256=_digest(row_ids),
            specimen_content_sha256=_digest(rows),
            source_projection_sha256=projection.source,
            coverage_projection_sha256=projection.coverage,
            answer_schema_projection_sha256=projection.answer_schema,
        ))
    receipt_map = {item.capability_id: item for item in receipts}
    assessments = []
    for grade in plan.grades:
        receipt_hashes = tuple(
            receipt_map[capability].digest()
            for capability in grade.cumulative_scope)
        seal = VerifiedAssessmentSeal(
            grade_id=grade.grade_id,
            cumulative_scope=grade.cumulative_scope,
            assessment_blueprint_sha256=grade.assessment_blueprint_sha256,
            capability_receipt_sha256s=receipt_hashes,
            seal_sha256="0" * 64,
        )
        assessments.append(replace(seal, seal_sha256=seal.expected_digest()))
    descriptors = _provider_descriptors(plan, bindings, source_registry)
    names = graph.get("tokens") if isinstance(graph, dict) else None
    if (not isinstance(names, list) or not names or
            any(not isinstance(name, str) or not name for name in names)):
        raise ValueError("FACTORY_EXECUTABLE_RELEASE_SEMANTIC_CATALOG_REQUIRED")
    return ExecutableVerificationReceipt(
        verification_seed=verification_seed,
        execution_plan_sha256=plan.digest(),
        source_binding_sha256=bindings.digest(),
        provider_descriptors_sha256=_digest(
            [asdict(item) for item in descriptors]),
        answer_modalities_sha256=_digest(
            [asdict(item) for item in answer_modalities]),
        semantic_catalog_sha256=_digest(tuple(names)),
        answer_heads_sha256=_digest(
            [asdict(item) for item in answer_heads]),
        capabilities=tuple(receipts),
        assessments=tuple(assessments),
    )


def compile_executable_factory_release(
        curriculum: CurriculumDefinition, source_bindings: SourceBindingSet,
        profile: CurriculumProfile, source_registry: SourceAdapterRegistry,
        answer_registry: AnswerModalityRegistry, *, source_root, graph: dict,
        verification_seed: int, legacy_course=None,
        predecessor: ExecutableFactoryRelease | None = None,
        lineage: PlanLineage | None = None) -> ExecutableFactoryRelease:
    """Compile and source-verify one immutable v2 FactoryRelease."""
    if (not isinstance(curriculum, CurriculumDefinition) or
            not isinstance(source_bindings, SourceBindingSet) or
            not isinstance(profile, CurriculumProfile) or
            not isinstance(source_registry, SourceAdapterRegistry) or
            not isinstance(answer_registry, AnswerModalityRegistry) or
            type(verification_seed) is not int):
        raise TypeError("FACTORY_EXECUTABLE_RELEASE_INVALID_INPUT")
    plan = compile_execution_plan(
        curriculum, profile, source_registry,
        source_bindings=source_bindings, answer_registry=answer_registry)
    answer_modalities = answer_registry.descriptors_for(plan)
    answer_heads = _answer_head_bindings(plan, graph, answer_registry)
    source_adapters = _provider_descriptors(
        plan, source_bindings, source_registry)
    verification = _verification_receipt(
        curriculum, source_bindings, plan, source_registry,
        answer_modalities, answer_heads, source_root=source_root, graph=graph,
        verification_seed=verification_seed, legacy_course=legacy_course)

    predecessor_sha = None
    transition = None
    if predecessor is not None:
        if not isinstance(predecessor, ExecutableFactoryRelease):
            raise TypeError("FACTORY_EXECUTABLE_RELEASE_PREDECESSOR_INVALID")
        predecessor.verify()
        transition = diff_execution_plans(
            predecessor.execution_plan, plan, lineage=lineage)
        if transition.semantic_geometry == SemanticGeometryChange.INCOMPATIBLE.value:
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_INCOMPATIBLE_GEOMETRY")
        predecessor_sha = predecessor.release_sha256
    elif lineage is not None:
        raise ValueError("FACTORY_EXECUTABLE_RELEASE_LINEAGE_WITHOUT_PREDECESSOR")

    release = ExecutableFactoryRelease(
        schema=SCHEMA,
        curriculum=curriculum,
        source_bindings=source_bindings,
        profile=profile,
        execution_plan=plan,
        semantic_catalog_sha256=verification.semantic_catalog_sha256,
        source_adapters=source_adapters,
        answer_modalities=answer_modalities,
        answer_heads=answer_heads,
        verification=verification,
        predecessor_release_sha256=predecessor_sha,
        transition=transition,
        release_sha256="0" * 64,
    )
    release = replace(release, release_sha256=release.expected_digest())
    release.verify()
    release.verify_semantic_catalog(graph)
    return release
