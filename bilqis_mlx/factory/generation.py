"""Grade-neutral specimen generation from a verified FactoryRelease."""
from __future__ import annotations

from .adapters import SourceAdapterRegistry, validate_instructional_constituents
from .model import FactoryRelease
from .execution import ExecutionPlan
from .curriculum_definition import (
    CurriculumDefinition, SourceBindingSet, from_legacy_course,
    validate_source_bindings,
)
from ..compatibility.source_adapter_resume import resume_adapter_compatible


_GRADE_A_DEVELOPMENT_PRESENTATION_IMPLEMENTATION = (
    "c451c3e6bf5ab538450c691d504230036b9a729ddfc67b53163c6a1f106d62a9")
_GRADE_A_1324082_IMPLEMENTATION = (
    "f8e5aec9398538adc633deabe9c41c485e69a96044b9b86a5f1075ce6e201778")
_GRADE_A_BASE_VARIATION_AXES = (
    "source-valid", "balanced-gold", "fresh-seed",
    "member-decoy-set-context-v1", "irrelevant-source-context-v2",
)
_GRADE_A_1324082_VARIATION_AXES = (
    *_GRADE_A_BASE_VARIATION_AXES, "generalization-only-source-context-v3",
)


def _is_1324082_rollback_adapter_pair(admitted, current) -> bool:
    """Recognize the exact Grade-A provider identity removed by ADR-099.

    This is intentionally one-way: a durable release admitted while 1324082 was
    active may resume on the reverted provider. No other implementation drift is
    accepted, and the reverted provider may not impersonate the removed one in a
    newly admitted release.
    """
    if admitted is None:
        return False
    return (
        admitted.adapter_id == current.adapter_id == "source.micro.predicates/v1" and
        admitted.generator_id == current.generator_id ==
        "bilqis_mlx.grade_a_probe.make_record" and
        admitted.accepted_oracle_ids == current.accepted_oracle_ids ==
        ("bilqis.mlx.grade-a-record-oracle/v2",) and
        admitted.cohort_generator_id == current.cohort_generator_id ==
        "bilqis.mlx.grade-a-live-constructor/v1" and
        admitted.teaching_option_ids == current.teaching_option_ids == () and
        admitted.profile_dimensions == current.profile_dimensions == () and
        admitted.implementation_sha256 == _GRADE_A_1324082_IMPLEMENTATION and
        current.implementation_sha256 == _GRADE_A_DEVELOPMENT_PRESENTATION_IMPLEMENTATION and
        len(admitted.cohort_releases) == len(current.cohort_releases) == 1 and
        admitted.cohort_releases[0][0] == current.cohort_releases[0][0] and
        admitted.cohort_releases[0][1] == _GRADE_A_1324082_IMPLEMENTATION and
        current.cohort_releases[0][1] == _GRADE_A_DEVELOPMENT_PRESENTATION_IMPLEMENTATION and
        admitted.variation_axes == _GRADE_A_1324082_VARIATION_AXES and
        current.variation_axes == _GRADE_A_BASE_VARIATION_AXES)


def runtime_adapter_for_release(
        source_root, graph, release, registry, execution, *,
        drift_code="FACTORY_EXECUTABLE_GENERATION_ADAPTER_DRIFT"):
    """Execute only the exact implementation bound by the admission receipt.

    Historical releases remain readable. A refactored provider requires its own
    verified admission; specimen replay cannot substitute a different identity.
    """
    binding = release.source_bindings.by_capability[execution.capability_id]
    registered = registry.require(binding.generator_id, binding.oracle_id)
    admitted = next((
        item for item in release.source_adapters
        if item.adapter_id == execution.provider_id), None)
    if (registered.descriptor != admitted and
            not _is_1324082_rollback_adapter_pair(
                admitted, registered.descriptor) and
            not resume_adapter_compatible(admitted, registered.descriptor)):
        raise ValueError(drift_code + ":" + execution.capability_id)
    return registered


def draw_release_rows(source_root, graph, release: FactoryRelease,
                      registry: SourceAdapterRegistry, *, seed: int,
                      capability: str | None = None, each: int | None = None) -> list[dict]:
    release.verify()
    if not isinstance(registry, SourceAdapterRegistry):
        raise TypeError("FACTORY_GENERATION_REGISTRY_REQUIRED")
    course = release.course
    selected = tuple(
        (grade, cap, count)
        for grade in course.grades
        for cap, (name, count) in zip(grade.capabilities, grade.exam_item_counts)
        if name == cap.id and (capability is None or cap.id == capability)
    )
    if capability is not None and capability not in course.capability_map:
        raise ValueError("FACTORY_GENERATION_UNKNOWN_CAPABILITY")
    if not selected:
        raise ValueError("FACTORY_GENERATION_EMPTY_SCOPE")
    rows = []
    for _, cap, default_count in selected:
        count = default_count if each is None else each
        if type(count) is not int or count < 1:
            raise ValueError("FACTORY_GENERATION_INVALID_COUNT")
        adapter = registry.require(cap.lesson_generator, cap.independent_oracle)
        if adapter.descriptor != release.source_adapter_map.get(adapter.descriptor.adapter_id):
            raise ValueError("FACTORY_GENERATION_ADAPTER_DRIFT:" + cap.id)
        batch = adapter.draw(
            source_root=source_root, graph=graph, course=course,
            capability=cap.id, seed=seed, each=count)
        if (len(batch) != count or
                any(row.get("capability") != cap.id for row in batch)):
            raise ValueError("FACTORY_GENERATION_ADAPTER_SCOPE_DRIFT:" + cap.id)
        answers = {family.kind: family.values for family in cap.answer_families}
        for row in batch:
            if (not isinstance(row.get("id"), str) or not row["id"] or
                    row.get("gold") not in answers.get(row.get("answer_kind", "binary"), ())):
                raise ValueError("FACTORY_GENERATION_ANSWER_CONTRACT_DRIFT:" + cap.id)
            if adapter.check(row, source_root=source_root, graph=graph, course=course) is not True:
                raise ValueError("FACTORY_GENERATION_SOURCE_ORACLE_DISAGREEMENT:" + cap.id)
        rows.extend(batch)
    expected = {cap.id: (each if each is not None else count)
                for _, cap, count in selected}
    actual = {cap: sum(row.get("capability") == cap for row in rows)
              for cap in expected}
    if actual != expected:
        raise ValueError("FACTORY_GENERATION_INCOMPLETE_RELEASE_SCOPE")
    return rows


def draw_execution_rows(
        source_root, graph, curriculum, plan: ExecutionPlan,
        registry: SourceAdapterRegistry, *, seed: int,
        source_bindings: SourceBindingSet | None = None,
        capability: str | None = None,
        each: int | None = None) -> list[dict]:
    """Generate from one compiled execution contract, including profile constraints."""
    adapter_context = curriculum
    if isinstance(curriculum, CurriculumDefinition):
        if source_bindings is None:
            raise ValueError("FACTORY_EXECUTION_GENERATION_SOURCE_BINDINGS_REQUIRED")
        validate_source_bindings(curriculum, source_bindings)
    else:
        if source_bindings is not None:
            raise ValueError("FACTORY_EXECUTION_GENERATION_LEGACY_BINDINGS_AMBIGUOUS")
        curriculum, source_bindings = from_legacy_course(curriculum)
    if (not isinstance(plan, ExecutionPlan) or
            plan.curriculum_sha256 != curriculum.digest() or
            plan.source_binding_sha256 != source_bindings.digest()):
        raise ValueError("FACTORY_EXECUTION_GENERATION_PLAN_BINDING_DRIFT")
    if not isinstance(registry, SourceAdapterRegistry):
        raise TypeError("FACTORY_EXECUTION_GENERATION_REGISTRY_REQUIRED")
    selected = tuple(
        item for item in plan.capabilities
        if capability is None or item.capability_id == capability)
    if capability is not None and capability not in plan.capability_map:
        raise ValueError("FACTORY_EXECUTION_GENERATION_UNKNOWN_CAPABILITY")
    if not selected:
        raise ValueError("FACTORY_EXECUTION_GENERATION_EMPTY_SCOPE")

    rows = []
    bindings = source_bindings.by_capability
    for execution in selected:
        count = execution.exam_item_count if each is None else each
        if type(count) is not int or count < 1:
            raise ValueError("FACTORY_EXECUTION_GENERATION_INVALID_COUNT")
        binding = bindings[execution.capability_id]
        adapter = registry.require(
            binding.generator_id, binding.oracle_id)
        if adapter.descriptor.adapter_id != execution.provider_id:
            raise ValueError(
                "FACTORY_EXECUTION_GENERATION_ADAPTER_DRIFT:"
                + execution.capability_id)
        adapter.descriptor.validate_profile_parameters(
            execution.provider_parameters)
        arguments = {
            "source_root": source_root,
            "graph": graph,
            "course": adapter_context,
            "capability": execution.capability_id,
            "seed": seed,
            "each": count,
        }
        if execution.provider_parameters:
            arguments["profile_parameters"] = dict(
                execution.provider_parameters)
        batch = adapter.draw(**arguments)
        if (len(batch) != count or
                any(row.get("capability") != execution.capability_id
                    for row in batch)):
            raise ValueError(
                "FACTORY_EXECUTION_GENERATION_SCOPE_DRIFT:"
                + execution.capability_id)
        answers = {
            family.kind: family.values for family in execution.answer_families}
        for row in batch:
            kind = row.get("answer_kind", "binary")
            if (not isinstance(row.get("id"), str) or not row["id"] or
                    row.get("gold") not in answers.get(kind, ())):
                raise ValueError(
                    "FACTORY_EXECUTION_GENERATION_ANSWER_DRIFT:"
                    + execution.capability_id)
            if adapter.check(
                    row, source_root=source_root, graph=graph,
                    course=adapter_context) is not True:
                raise ValueError(
                    "FACTORY_EXECUTION_GENERATION_SOURCE_ORACLE_DISAGREEMENT:"
                    + execution.capability_id)
            validate_instructional_constituents(
                row, curriculum=curriculum, plan=plan,
                capability=execution.capability_id, adapter=adapter)
        rows.extend(batch)
    return rows


def draw_executable_release_rows(
        source_root, graph, release, registry: SourceAdapterRegistry, *,
        seed: int, capability: str | None = None,
        each: int | None = None) -> list[dict]:
    """Generate only from one admitted v2 release and its compiled projections."""
    from .executable_release import ExecutableFactoryRelease

    if not isinstance(release, ExecutableFactoryRelease):
        raise TypeError("FACTORY_EXECUTABLE_GENERATION_RELEASE_REQUIRED")
    if not isinstance(registry, SourceAdapterRegistry):
        raise TypeError("FACTORY_EXECUTABLE_GENERATION_REGISTRY_REQUIRED")
    release.verify()
    release.verify_semantic_catalog(graph)

    if capability is None:
        selected = release.execution_plan.capabilities
    else:
        selected_item = release.execution_plan.capability_map.get(capability)
        if selected_item is None:
            raise ValueError("FACTORY_EXECUTABLE_GENERATION_UNKNOWN_CAPABILITY")
        selected = (selected_item,)
    for execution in selected:
        runtime_adapter_for_release(
            source_root, graph, release, registry, execution)

    return draw_execution_rows(
        source_root, graph, release.curriculum, release.execution_plan, registry,
        source_bindings=release.source_bindings,
        seed=seed, capability=capability, each=each)
