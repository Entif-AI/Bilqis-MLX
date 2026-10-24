"""Grade-neutral specimen generation from a verified FactoryRelease."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json

from .adapters import SourceAdapterRegistry
from .model import FactoryRelease
from .execution import ExecutionPlan
from .curriculum_definition import (
    CurriculumDefinition, SourceBindingSet, from_legacy_course,
    validate_source_bindings,
)


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


def _runtime_adapter_contract(descriptor) -> dict:
    """Return provider identity that must remain stable across code refactors.

    Implementation and historical cohort-code digests are evidence about exact
    source bytes, not the semantic adapter contract itself. A newer
    implementation may execute an older admitted release only after it
    reproduces that release's sealed capability specimens exactly.
    """
    contract = asdict(descriptor)
    contract.pop("implementation_sha256")
    releases = contract.pop("cohort_releases")
    contract["cohort_release_ids"] = tuple(name for name, _ in releases)
    return contract


def _requalifies_sealed_capability(
        source_root, graph, release, registry, execution, *, legacy_course=None) -> bool:
    receipt = next((
        item for item in release.verification.capabilities
        if item.capability_id == execution.capability_id), None)
    if receipt is None:
        return False
    try:
        rows = draw_execution_rows(
            source_root, graph, release.curriculum, release.execution_plan,
            registry, source_bindings=release.source_bindings,
            seed=receipt.verification_seed,
            capability=execution.capability_id, each=receipt.specimen_count)
    except (KeyError, TypeError, ValueError):
        return False
    return (
        len(rows) == receipt.specimen_count and
        _digest(tuple(row["id"] for row in rows)) == receipt.specimen_ids_sha256 and
        _digest(rows) == receipt.specimen_content_sha256
    )


def runtime_adapter_for_release(
        source_root, graph, release, registry, execution, *, legacy_course=None,
        drift_code="FACTORY_EXECUTABLE_GENERATION_ADAPTER_DRIFT"):
    """Resolve a runtime provider without confusing refactoring with source drift.

    Exact descriptor identity is the fast path. If only implementation evidence
    changed while the declared semantic adapter contract stayed intact, require
    the current implementation to reproduce the admitted release's sealed
    capability specimens byte-for-byte before allowing execution.
    """
    binding = release.source_bindings.by_capability[execution.capability_id]
    registered = registry.require(binding.generator_id, binding.oracle_id)
    admitted = next((
        item for item in release.source_adapters
        if item.adapter_id == execution.provider_id), None)
    compatible = registered.descriptor == admitted
    if (not compatible and admitted is not None and
            _runtime_adapter_contract(registered.descriptor) ==
            _runtime_adapter_contract(admitted)):
        compatible = _requalifies_sealed_capability(
            source_root, graph, release, registry, execution,
            legacy_course=legacy_course)
    if not compatible:
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
        rows.extend(batch)
    return rows


def draw_executable_release_rows(
        source_root, graph, release, registry: SourceAdapterRegistry, *,
        seed: int, legacy_course=None, capability: str | None = None,
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
            source_root, graph, release, registry, execution,
            legacy_course=legacy_course)

    return draw_execution_rows(
        source_root, graph, release.curriculum, release.execution_plan, registry,
        source_bindings=release.source_bindings,
        seed=seed, capability=capability, each=each)
