"""School policy for append-only semantic-catalog admission."""
from __future__ import annotations

from dataclasses import dataclass

from ..factory.executable_release import ExecutableFactoryRelease
from ..factory.execution import CurriculumProfile
from ..live_grade_c import expanded_graph
from .school import (
    boolean_entry_profile,
    numeric_foundation_profile,
    with_disabled_future_grades,
)


@dataclass(frozen=True)
class CatalogProfileTransition:
    profile: CurriculumProfile
    graph: dict


def numeric_entry_transition(
        release: ExecutableFactoryRelease, graph: dict, *,
        full_boolean: bool, maximum: int = 3) -> CatalogProfileTransition:
    """Build the next canonical grade-prefix profile plus its admitted ABI."""
    if not isinstance(release, ExecutableFactoryRelease):
        raise TypeError("FACTORY_CATALOG_RELEASE_REQUIRED")
    release.verify()
    next_index = len(release.execution_plan.grades)
    if not 0 <= next_index < len(release.curriculum.grades):
        raise ValueError("FACTORY_CATALOG_NO_DISABLED_GRADE")
    next_grade = release.curriculum.grades[next_index]
    boolean = boolean_entry_profile(full=full_boolean)
    profile = numeric_foundation_profile(
        boolean,
        maximum=maximum,
        grade_id=next_grade.grade_id,
        capability_ids=tuple(
            capability.capability_id for capability in next_grade.capabilities),
    )
    future = tuple(
        grade.grade_id
        for grade in release.curriculum.grades[next_index + 1:])
    profile = with_disabled_future_grades(profile, future)
    return CatalogProfileTransition(
        profile=profile,
        graph=expanded_graph(graph),
    )
