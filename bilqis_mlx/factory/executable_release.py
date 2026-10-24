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


class _ReleaseError:
    """Stable legacy wire codes owned by the executable-release contract."""

    MODALITY_DRIFT = "FACTORY_EXECUTABLE_RELEASE_MODALITY_DRIFT"
    PROVIDER_DRIFT = "FACTORY_EXECUTABLE_RELEASE_PROVIDER_DRIFT"
    ANSWER_HEAD_DRIFT = "FACTORY_EXECUTABLE_RELEASE_ANSWER_HEAD_DRIFT"
    CATALOG_INVALID = "FACTORY_EXECUTABLE_RELEASE_CATALOG_INVALID"
    CATALOG_DRIFT = "FACTORY_EXECUTABLE_RELEASE_CATALOG_DRIFT"
    SEMANTIC_CATALOG_REQUIRED = "FACTORY_EXECUTABLE_RELEASE_SEMANTIC_CATALOG_REQUIRED"
    VERIFICATION_INVALID = "FACTORY_EXECUTABLE_RELEASE_VERIFICATION_INVALID"
    VERIFICATION_DRIFT = "FACTORY_EXECUTABLE_RELEASE_VERIFICATION_DRIFT"
    ASSESSMENT_DRIFT = "FACTORY_EXECUTABLE_RELEASE_ASSESSMENT_DRIFT"
    LINEAGE_DRIFT = "FACTORY_EXECUTABLE_RELEASE_LINEAGE_DRIFT"


def _require(condition: bool, code: str) -> None:
    """Fail one named release invariant without duplicating its wire identity."""
    if not condition:
        raise ValueError(code)


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
        _require(
            bool(self.capability_id) and type(self.verification_seed) is int and
            type(self.specimen_count) is int and self.specimen_count >= 1,
            _ReleaseError.VERIFICATION_INVALID,
        )
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
        _require(
            type(self.verification_seed) is int and
            bool(self.capabilities) and bool(self.assessments),
            _ReleaseError.VERIFICATION_INVALID,
        )
        for value in (
                self.execution_plan_sha256, self.source_binding_sha256,
                self.provider_descriptors_sha256, self.answer_modalities_sha256,
                self.semantic_catalog_sha256, self.answer_heads_sha256):
            _require_sha256(
                value, "FACTORY_EXECUTABLE_RELEASE_VERIFICATION_DIGEST_INVALID")


@dataclass(frozen=True)
class ExecutableAdmissionReceipt:
    factory_release_sha256: str
    execution_plan_sha256: str
    curriculum_sha256: str
    source_binding_sha256: str
    semantic_catalog_sha256: str
    semantic_graph_sha256: str
    student_sha256: str
    optimizer_step: int

    def __post_init__(self) -> None:
        for value in (
                self.factory_release_sha256, self.execution_plan_sha256,
                self.curriculum_sha256, self.source_binding_sha256,
                self.semantic_catalog_sha256, self.semantic_graph_sha256,
                self.student_sha256):
            _require_sha256(
                value, "FACTORY_EXECUTABLE_ADMISSION_DIGEST_INVALID")
        if type(self.optimizer_step) is not int or self.optimizer_step < 0:
            raise ValueError("FACTORY_EXECUTABLE_ADMISSION_STEP_INVALID")

    def verify(self, release: "ExecutableFactoryRelease") -> None:
        if not isinstance(release, ExecutableFactoryRelease):
            raise TypeError("FACTORY_EXECUTABLE_ADMISSION_RELEASE_REQUIRED")
        release.verify()
        if (self.factory_release_sha256 != release.release_sha256 or
                self.execution_plan_sha256 != release.execution_plan.digest() or
                self.curriculum_sha256 != release.curriculum.digest() or
                self.source_binding_sha256 != release.source_bindings.digest() or
                self.semantic_catalog_sha256 != release.semantic_catalog_sha256):
            raise ValueError("FACTORY_EXECUTABLE_ADMISSION_RELEASE_MISMATCH")


@dataclass(frozen=True)
class ExecutableFactoryRelease:
    """Version-2 FactoryRelease; the complete executable authority artifact."""

    schema: str
    curriculum: CurriculumDefinition
    source_bindings: SourceBindingSet
    profile: CurriculumProfile
    execution_plan: ExecutionPlan
    semantic_catalog: tuple[str, ...]
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
        _require(
            bool(self.semantic_catalog) and
            len(set(self.semantic_catalog)) == len(self.semantic_catalog) and
            all(isinstance(item, str) and item for item in self.semantic_catalog),
            _ReleaseError.CATALOG_INVALID,
        )
        _require_sha256(
            self.semantic_catalog_sha256,
            _ReleaseError.CATALOG_INVALID)
        _require_sha256(
            self.release_sha256, "FACTORY_EXECUTABLE_RELEASE_DIGEST_INVALID")

    def manifest(self) -> dict:
        return {
            "schema": self.schema,
            "curriculum": asdict(self.curriculum),
            "source_bindings": asdict(self.source_bindings),
            "profile": asdict(self.profile),
            "execution_plan": asdict(self.execution_plan),
            "semantic_catalog": self.semantic_catalog,
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
        answer_kinds = _verify_release_structure(self)
        _verify_release_providers(self)
        _verify_release_answers(self, answer_kinds)
        _verify_release_evidence(self)
        _verify_release_assessments(self)
        _verify_release_lineage(self)

    def verify_semantic_catalog(self, graph: dict) -> None:
        """Bind the offline release artifact to the exact loaded semantic ABI."""
        names = graph.get("tokens") if isinstance(graph, dict) else None
        _require(
            isinstance(names, list) and bool(names) and
            len(set(names)) == len(names) and
            all(isinstance(name, str) and name for name in names),
            _ReleaseError.CATALOG_INVALID,
        )
        _require(
            tuple(names) == self.semantic_catalog and
            _digest(tuple(names)) == self.semantic_catalog_sha256,
            _ReleaseError.CATALOG_DRIFT,
        )
        for head in self.answer_heads:
            if any(
                    token_id >= len(names) or
                    names[token_id] != identity
                    for identity, token_id in zip(
                        head.semantic_identities, head.token_ids)):
                raise ValueError(
                    "FACTORY_EXECUTABLE_RELEASE_ANSWER_HEAD_CATALOG_DRIFT")

    def verify_successor_of(self, predecessor: "ExecutableFactoryRelease") -> None:
        """Verify persisted lineage against the actual predecessor artifact."""
        if not isinstance(predecessor, ExecutableFactoryRelease):
            raise TypeError("FACTORY_EXECUTABLE_RELEASE_PREDECESSOR_REQUIRED")
        predecessor.verify()
        self.verify()
        if (self.predecessor_release_sha256 != predecessor.release_sha256 or
                self.transition is None or
                self.transition.previous_plan_sha256 !=
                predecessor.execution_plan.digest() or
                self.transition.previous_curriculum_sha256 !=
                predecessor.execution_plan.curriculum_sha256 or
                self.transition.previous_source_binding_sha256 !=
                predecessor.execution_plan.source_binding_sha256):
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_PREDECESSOR_DRIFT")
        previous = predecessor.semantic_catalog
        current = self.semantic_catalog
        if current == previous:
            expected = SemanticGeometryChange.UNCHANGED.value
        elif current[:len(previous)] == previous:
            expected = SemanticGeometryChange.APPEND_ONLY_EXPANSION.value
        else:
            expected = SemanticGeometryChange.INCOMPATIBLE.value
        if (expected == SemanticGeometryChange.INCOMPATIBLE.value or
                self.transition.semantic_geometry != expected):
            raise ValueError(_ReleaseError.LINEAGE_DRIFT)

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
                semantic_catalog=_tuples(payload["semantic_catalog"]),
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


def _verify_release_structure(release: ExecutableFactoryRelease) -> tuple[str, ...]:
    _require(
        release.release_sha256 == release.expected_digest(),
        "FACTORY_EXECUTABLE_RELEASE_CONTENT_DRIFT",
    )
    answer_kinds = tuple(item.kind for item in release.answer_modalities)
    _require(
        len(set(answer_kinds)) == len(answer_kinds),
        _ReleaseError.MODALITY_DRIFT,
    )
    validate_curriculum_definition(release.curriculum, answer_kinds=answer_kinds)
    validate_source_bindings(release.curriculum, release.source_bindings)
    _require(
        release.profile.profile_id == release.execution_plan.profile_id,
        "FACTORY_EXECUTABLE_RELEASE_PROFILE_DRIFT",
    )
    _require(
        release.curriculum.digest() == release.execution_plan.curriculum_sha256 and
        release.source_bindings.digest() == release.execution_plan.source_binding_sha256,
        "FACTORY_EXECUTABLE_RELEASE_PLAN_BINDING_DRIFT",
    )
    return answer_kinds


def _verify_release_providers(release: ExecutableFactoryRelease) -> None:
    providers = {item.adapter_id: item for item in release.source_adapters}
    _require(
        len(providers) == len(release.source_adapters),
        _ReleaseError.PROVIDER_DRIFT,
    )
    bindings = release.source_bindings.by_capability
    for execution in release.execution_plan.capabilities:
        provider = providers.get(execution.provider_id)
        binding = bindings.get(execution.capability_id)
        _require(
            provider is not None and binding is not None and
            execution.provider_implementation_sha256 == provider.implementation_sha256 and
            binding.source_anchor == execution.source_anchor and
            binding.generator_id == provider.generator_id and
            execution.oracle_id == binding.oracle_id and
            binding.oracle_id in provider.accepted_oracle_ids,
            _ReleaseError.PROVIDER_DRIFT,
        )
        provider.validate_profile_parameters(execution.provider_parameters)


def _verify_release_answers(
        release: ExecutableFactoryRelease, answer_kinds: tuple[str, ...]) -> None:
    used_kinds = tuple(dict.fromkeys(
        family.kind for capability in release.execution_plan.capabilities
        for family in capability.answer_families))
    _require(
        set(used_kinds) <= set(answer_kinds) and
        used_kinds == tuple(kind for kind in answer_kinds if kind in set(used_kinds)),
        _ReleaseError.MODALITY_DRIFT,
    )
    modalities = {item.kind: item for item in release.answer_modalities}
    heads = {item.kind: item for item in release.answer_heads}
    _require(tuple(heads) == used_kinds, _ReleaseError.ANSWER_HEAD_DRIFT)
    for kind, head in heads.items():
        descriptor = modalities[kind]
        _require(
            head.modality_id == descriptor.adapter_id and
            head.implementation_sha256 == descriptor.implementation_sha256,
            _ReleaseError.ANSWER_HEAD_DRIFT,
        )


def _verify_release_evidence(release: ExecutableFactoryRelease) -> None:
    verification = release.verification
    _require(
        _digest(release.semantic_catalog) == release.semantic_catalog_sha256 and
        verification.semantic_catalog_sha256 == release.semantic_catalog_sha256,
        _ReleaseError.CATALOG_DRIFT,
    )
    _require(
        verification.execution_plan_sha256 == release.execution_plan.digest() and
        verification.source_binding_sha256 == release.source_bindings.digest() and
        verification.provider_descriptors_sha256 ==
            _digest([asdict(item) for item in release.source_adapters]) and
        verification.answer_modalities_sha256 ==
            _digest([asdict(item) for item in release.answer_modalities]) and
        verification.answer_heads_sha256 ==
            _digest([asdict(item) for item in release.answer_heads]),
        _ReleaseError.VERIFICATION_DRIFT,
    )
    capability_ids = tuple(
        item.capability_id for item in release.execution_plan.capabilities)
    receipts = verification.capabilities
    _require(
        tuple(item.capability_id for item in receipts) == capability_ids,
        _ReleaseError.VERIFICATION_DRIFT,
    )
    projections = {
        item.capability_id: item
        for item in release.execution_plan.capability_projection_digests}
    executions = release.execution_plan.capability_map
    for receipt in receipts:
        execution = executions[receipt.capability_id]
        projection = projections[receipt.capability_id]
        _require(
            receipt.verification_seed == verification.verification_seed and
            receipt.specimen_count == execution.exam_item_count and
            receipt.source_projection_sha256 == projection.source and
            receipt.coverage_projection_sha256 == projection.coverage and
            receipt.answer_schema_projection_sha256 == projection.answer_schema,
            _ReleaseError.VERIFICATION_DRIFT,
        )


def _verify_release_assessments(release: ExecutableFactoryRelease) -> None:
    verification = release.verification
    receipt_map = {
        item.capability_id: item for item in verification.capabilities}
    _require(
        tuple(item.grade_id for item in verification.assessments) ==
        tuple(item.grade_id for item in release.execution_plan.grades),
        _ReleaseError.ASSESSMENT_DRIFT,
    )
    for seal, grade in zip(verification.assessments, release.execution_plan.grades):
        expected_receipts = tuple(
            receipt_map[capability].digest() for capability in grade.cumulative_scope)
        _require(
            seal.cumulative_scope == grade.cumulative_scope and
            seal.assessment_blueprint_sha256 == grade.assessment_blueprint_sha256 and
            seal.capability_receipt_sha256s == expected_receipts and
            seal.seal_sha256 == seal.expected_digest(),
            _ReleaseError.ASSESSMENT_DRIFT,
        )


def _verify_release_lineage(release: ExecutableFactoryRelease) -> None:
    if release.predecessor_release_sha256 is None:
        _require(release.transition is None, _ReleaseError.LINEAGE_DRIFT)
        return
    transition = release.transition
    _require(
        transition is not None and
        transition.next_plan_sha256 == release.execution_plan.digest() and
        transition.next_curriculum_sha256 == release.execution_plan.curriculum_sha256 and
        transition.next_source_binding_sha256 == release.execution_plan.source_binding_sha256 and
        transition.semantic_geometry != SemanticGeometryChange.INCOMPATIBLE.value,
        _ReleaseError.LINEAGE_DRIFT,
    )


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
            source_bindings=bindings,
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
    _require(
        isinstance(names, list) and bool(names) and
        all(isinstance(name, str) and name for name in names),
        _ReleaseError.SEMANTIC_CATALOG_REQUIRED,
    )
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
    canonical_kinds = tuple(dict.fromkeys(
        family.kind
        for grade in curriculum.grades
        for capability in grade.capabilities
        for family in capability.answer_families))
    answer_modalities = tuple(
        answer_registry.require(kind).descriptor
        for kind in canonical_kinds)
    answer_heads = _answer_head_bindings(plan, graph, answer_registry)
    source_adapters = _provider_descriptors(
        plan, source_bindings, source_registry)
    semantic_catalog = tuple(
        graph.get("tokens") if isinstance(graph, dict) else ())
    _require(
        bool(semantic_catalog) and
        len(set(semantic_catalog)) == len(semantic_catalog) and
        all(isinstance(item, str) and item for item in semantic_catalog),
        _ReleaseError.SEMANTIC_CATALOG_REQUIRED,
    )
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
        derived_lineage = PlanLineage.from_semantic_catalogs(
            predecessor.execution_plan, plan,
            predecessor.semantic_catalog, semantic_catalog)
        if lineage is not None and lineage != derived_lineage:
            raise ValueError("FACTORY_EXECUTABLE_RELEASE_LINEAGE_DRIFT")
        lineage = derived_lineage
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
        semantic_catalog=semantic_catalog,
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
    if predecessor is not None:
        release.verify_successor_of(predecessor)
    return release


def compile_successor_profile_release(
        predecessor: ExecutableFactoryRelease,
        profile: CurriculumProfile,
        source_registry: SourceAdapterRegistry,
        answer_registry: AnswerModalityRegistry, *,
        source_root, graph: dict, verification_seed: int,
        legacy_course=None) -> ExecutableFactoryRelease:
    """Recompile one profile over the predecessor's immutable authorities."""
    if not isinstance(predecessor, ExecutableFactoryRelease):
        raise TypeError("FACTORY_EXECUTABLE_RELEASE_PREDECESSOR_INVALID")
    predecessor.verify()
    return compile_executable_factory_release(
        predecessor.curriculum,
        predecessor.source_bindings,
        profile,
        source_registry,
        answer_registry,
        source_root=source_root,
        graph=graph,
        verification_seed=verification_seed,
        legacy_course=legacy_course,
        predecessor=predecessor,
    )


def admit_executable_factory_release(
        release: ExecutableFactoryRelease, *, student_sha256: str,
        optimizer_step: int, semantic_graph_sha256: str,
        graph: dict) -> ExecutableAdmissionReceipt:
    """Bind one verified v2 release to an exact causal-student baseline."""
    if not isinstance(release, ExecutableFactoryRelease):
        raise TypeError("FACTORY_EXECUTABLE_ADMISSION_RELEASE_REQUIRED")
    release.verify()
    release.verify_semantic_catalog(graph)
    receipt = ExecutableAdmissionReceipt(
        factory_release_sha256=release.release_sha256,
        execution_plan_sha256=release.execution_plan.digest(),
        curriculum_sha256=release.curriculum.digest(),
        source_binding_sha256=release.source_bindings.digest(),
        semantic_catalog_sha256=release.semantic_catalog_sha256,
        semantic_graph_sha256=semantic_graph_sha256,
        student_sha256=student_sha256,
        optimizer_step=optimizer_step,
    )
    receipt.verify(release)
    return receipt


def answer_heads_from_executable_release(
        release: ExecutableFactoryRelease, graph: dict) -> dict:
    """Return the admitted typed readout without grade/release reconstruction."""
    if not isinstance(release, ExecutableFactoryRelease):
        raise TypeError("FACTORY_EXECUTABLE_RELEASE_REQUIRED")
    release.verify()
    release.verify_semantic_catalog(graph)
    names = graph["tokens"]
    result = {
        "semantic_token": {
            "values": list(names),
            "token_ids": list(range(len(names))),
        },
    }
    modalities = {
        modality.kind: modality for modality in release.answer_modalities
    }
    for head in release.answer_heads:
        modality = modalities[head.kind]
        result[head.kind] = {
            "values": list(head.values),
            "token_ids": list(head.token_ids),
            "modality_id": modality.adapter_id,
            "implementation_sha256": modality.implementation_sha256,
        }
    return result
