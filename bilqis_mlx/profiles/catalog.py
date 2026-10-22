"""School policy for append-only semantic-catalog admission."""
from __future__ import annotations

from dataclasses import dataclass

from ..factory.executable_release import ExecutableFactoryRelease
from ..factory.execution import (
    CapabilityProfile,
    CurriculumProfile,
    GradeProfile,
)
from ..live_grade_c import expanded_graph
from ..semantics.core import Literal
from ..semantics.numeric import evaluate
from ..source_adapters.numeric import decode
from .school import (
    boolean_entry_profile,
    numeric_foundation_profile,
    with_disabled_future_grades,
)


@dataclass(frozen=True)
class CatalogProfileTransition:
    profile: CurriculumProfile
    graph: dict
    numeric_scope_final_maximum: int | None = None


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
    boolean = boolean_entry_profile(full=True) if full_boolean else release.profile
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
    from ..numeric_staircase import FINAL_MAXIMUM
    return CatalogProfileTransition(
        profile=profile,
        graph=expanded_graph(graph),
        numeric_scope_final_maximum=(
            FINAL_MAXIMUM if maximum < FINAL_MAXIMUM else None),
    )


def _validate_numeric_scope_target(
        release: ExecutableFactoryRelease, maximum: int, *,
        require_active_grade: bool) -> None:
    """Keep the historical numeric-scope boundary contract in one owner."""
    is_release = isinstance(release, ExecutableFactoryRelease)
    if is_release:
        release.verify()
    active_grade_missing = (
        is_release and require_active_grade and not release.execution_plan.grades)
    if (not is_release or type(maximum) is not int or
            not 1 <= maximum <= 10 or active_grade_missing):
        raise ValueError("FACTORY_NUMERIC_SCOPE_ADVANCE_INVALID")


def numeric_scope_profile(
        release: ExecutableFactoryRelease, maximum: int) -> CurriculumProfile:
    """Project one exact bounded numeric domain over the active numeric grade."""
    _validate_numeric_scope_target(
        release, maximum, require_active_grade=True)
    active_grade = release.execution_plan.grades[-1]
    canonical_grade = next(
        grade for grade in release.curriculum.grades
        if grade.grade_id == active_grade.grade_id)
    all_ids = tuple(
        capability.capability_id for capability in canonical_grade.capabilities)
    from ..numeric_staircase import FINAL_MAXIMUM, FOUNDATIONS
    enabled = (all_ids if maximum >= FINAL_MAXIMUM else
               all_ids[:len(FOUNDATIONS)])
    numbers = tuple(str(index) for index in range(maximum + 1))
    numeric_grade = GradeProfile(
        active_grade.grade_id,
        enabled_capabilities=enabled,
        capabilities=tuple(CapabilityProfile(
            capability_id,
            provider_parameters=(("numbers", numbers),),
            answer_family_values=(("numeric_active", numbers),),
        ) for capability_id in enabled),
    )
    prior = tuple(
        grade for grade in release.profile.grades
        if grade.grade_id != active_grade.grade_id)
    future = tuple(
        GradeProfile(grade.grade_id, enabled_capabilities=())
        for grade in release.curriculum.grades[len(release.execution_plan.grades):]
        if grade.grade_id != active_grade.grade_id)
    return CurriculumProfile(
        f"{release.profile.profile_id.rsplit('/numeric-0-', 1)[0]}"
        f"/numeric-0-{maximum}",
        grades=(*prior, numeric_grade, *future),
    )


def next_numeric_scope_profile(
        release: ExecutableFactoryRelease, *, final_maximum: int | None = None
        ) -> CurriculumProfile | None:
    """Return the next bounded numeric-domain profile, preserving other grades."""
    from ..numeric_staircase import FINAL_MAXIMUM
    if final_maximum is None:
        final_maximum = FINAL_MAXIMUM
    _validate_numeric_scope_target(
        release, final_maximum, require_active_grade=False)
    if not release.execution_plan.grades:
        return None
    active_grade = release.execution_plan.grades[-1]
    executions = tuple(
        capability for capability in release.execution_plan.capabilities
        if capability.grade_id == active_grade.grade_id)
    domains = {
        family.values
        for capability in executions
        for family in capability.answer_families
        if family.kind == "numeric_active"
    }
    if not domains:
        return None
    if len(domains) != 1:
        raise ValueError("FACTORY_NUMERIC_SCOPE_DOMAIN_INCONSISTENT")
    values = next(iter(domains))
    if values != tuple(str(index) for index in range(len(values))):
        raise ValueError("FACTORY_NUMERIC_SCOPE_DOMAIN_INVALID")
    maximum = len(values) - 1
    if maximum >= final_maximum:
        return None
    return numeric_scope_profile(release, maximum + 1)


def numeric_row_in_scope(row: dict, maximum: int) -> bool:
    """Keep wider numeric mistakes deferred without grade-ID dispatch."""
    if type(maximum) is not int or maximum < 0:
        raise ValueError("FACTORY_NUMERIC_SCOPE_MAXIMUM_INVALID")
    symbols = tuple((row.get("record") or {}).get("symbols", ()))
    numeric_symbols = tuple(
        symbol for symbol in symbols
        if isinstance(symbol, str) and symbol.startswith("school.number."))
    if not numeric_symbols:
        return True
    if any(
            int(symbol.removeprefix("school.number.")) > maximum
            for symbol in numeric_symbols):
        return False

    def bounded(node):
        if node.type_name == "Number" and evaluate(node) > maximum:
            return False
        if isinstance(node, Literal):
            return True
        return all(bounded(child) for child in node.arguments)

    # The numeric prefix codec accepts a list of catalog symbols, not the
    # immutable tuple used for the scope precheck above.
    return bounded(decode(list(symbols)))
