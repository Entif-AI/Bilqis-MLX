"""Grade-neutral specimen generation from a verified FactoryRelease."""
from __future__ import annotations

from .adapters import SourceAdapterRegistry
from .model import FactoryRelease


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
        batch = adapter.draw(
            source_root=source_root, graph=graph, course=course,
            capability=cap.id, seed=seed, each=count)
        if (len(batch) != count or
                any(row.get("capability") != cap.id for row in batch)):
            raise ValueError("FACTORY_GENERATION_ADAPTER_SCOPE_DRIFT:" + cap.id)
        rows.extend(batch)
    expected = {cap.id: (each if each is not None else count)
                for _, cap, count in selected}
    actual = {cap: sum(row.get("capability") == cap for row in rows)
              for cap in expected}
    if actual != expected:
        raise ValueError("FACTORY_GENERATION_INCOMPLETE_RELEASE_SCOPE")
    return rows
