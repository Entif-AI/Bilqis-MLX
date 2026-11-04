"""Executable Factory release compilation and successor construction."""
from __future__ import annotations
from dataclasses import asdict, replace
from ..adapters import SourceAdapterRegistry
from ..answers import AnswerModality, AnswerModalityRegistry, compile_answer_heads
from ..curriculum_definition import CurriculumDefinition, SourceBindingSet
from ..execution import (CurriculumProfile, ExecutionPlan, PlanLineage,
                         SemanticGeometryChange, compile_execution_plan,
                         diff_execution_plans)
from ..generation import draw_execution_rows
from ..model import SourceAdapter
from .common import SCHEMA, _ReleaseError, _digest, _require
from .records import (AnswerHeadBinding, CapabilityVerificationReceipt,
                      ExecutableVerificationReceipt, VerifiedAssessmentSeal)
from .release import ExecutableFactoryRelease

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
        verification_seed: int) -> ExecutableVerificationReceipt:
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
        verification_seed: int,
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
    semantic_graph_sha256 = _digest(graph)
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
        verification_seed=verification_seed)

    predecessor_sha, transition = _prepare_predecessor_transition(
        predecessor, plan, semantic_catalog, lineage)
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
        semantic_graph_sha256=semantic_graph_sha256,
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
        source_root, graph: dict, verification_seed: int) -> ExecutableFactoryRelease:
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
        predecessor=predecessor,
    )



def _prepare_predecessor_transition(predecessor, plan, semantic_catalog, lineage):
    """Verify predecessor custody and derive the exact semantic transition."""
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

    return predecessor_sha, transition
