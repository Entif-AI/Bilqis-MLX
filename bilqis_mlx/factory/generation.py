"""Grade-neutral specimen generation from a verified FactoryRelease."""
from __future__ import annotations

from .adapters import SourceAdapterRegistry
from .model import FactoryRelease
from .execution import ExecutionPlan


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


def draw_execution_rows(source_root, graph, course, plan: ExecutionPlan,
                        registry: SourceAdapterRegistry, *, seed: int,
                        capability: str | None = None,
                        each: int | None = None) -> list[dict]:
    """Generate from one compiled execution contract, including profile constraints."""
    if not isinstance(plan, ExecutionPlan) or plan.course_sha256 != course.digest():
        raise ValueError("FACTORY_EXECUTION_GENERATION_PLAN_COURSE_DRIFT")
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
    canonical = course.capability_map
    for execution in selected:
        count = execution.exam_item_count if each is None else each
        if type(count) is not int or count < 1:
            raise ValueError("FACTORY_EXECUTION_GENERATION_INVALID_COUNT")
        declared = canonical[execution.capability_id]
        adapter = registry.require(
            declared.lesson_generator, declared.independent_oracle)
        if adapter.descriptor.adapter_id != execution.provider_id:
            raise ValueError(
                "FACTORY_EXECUTION_GENERATION_ADAPTER_DRIFT:"
                + execution.capability_id)
        adapter.descriptor.validate_profile_parameters(
            execution.provider_parameters)
        arguments = {
            "source_root": source_root,
            "graph": graph,
            "course": course,
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
                    course=course) is not True:
                raise ValueError(
                    "FACTORY_EXECUTION_GENERATION_SOURCE_ORACLE_DISAGREEMENT:"
                    + execution.capability_id)
        rows.extend(batch)
    return rows
