"""Historical same-grade and next-release profile transitions."""
from __future__ import annotations

from dataclasses import dataclass
from .providers import (
    BOOLEAN_RELEASE, BOOLEAN_COMPOSITE_RELEASE, BOOLEAN_IDENTIFICATION_RELEASE,
    INITIAL_RELEASE, MINIMAL_BOOLEAN_RELEASE, FULL_BOOLEAN_RELEASES,
    boolean_successor, minimal_boolean_successor, boolean_composite_successor,
    boolean_identification_successor, numeric_successor,
)

SAME_GRAPH_TRANSITION = "SAME_GRAPH"
SAME_GRADE_TRANSITION = "SAME_GRADE"
GRAPH_GROWTH_TRANSITION = "GRAPH_GROWTH"

@dataclass(frozen=True)
class SuccessorPlan:
    successor: object
    transition: str


def default_resume_replacement(current_course, grade_a_course, source_root,
                               *, full_grade_b: bool = False):
    """Return the default neural-inert profile replacement for an existing run."""
    if full_grade_b or current_course.version == MINIMAL_BOOLEAN_RELEASE:
        return None
    if current_course.version in FULL_BOOLEAN_RELEASES:
        if (len(current_course.grades) != len(grade_a_course.grades) + 1 or
                current_course.grades[:-1] != grade_a_course.grades):
            raise ValueError("MINIMAL_GRADE_B_REPLACEMENT_REQUIRES_DIRECT_SUCCESSOR")
        return minimal_boolean_successor(grade_a_course, source_root)
    return None


def next_successor_plan(current_course, source_root, *, full_grade_b: bool = False) -> SuccessorPlan | None:
    """Provider-owned successor declaration for the current admitted release."""
    if current_course.version == INITIAL_RELEASE:
        successor = (boolean_successor(current_course, source_root) if full_grade_b
                     else minimal_boolean_successor(current_course, source_root))
        return SuccessorPlan(successor, SAME_GRAPH_TRANSITION)
    if current_course.version == BOOLEAN_RELEASE:
        return SuccessorPlan(
            boolean_composite_successor(current_course, source_root),
            SAME_GRADE_TRANSITION)
    if current_course.version == BOOLEAN_COMPOSITE_RELEASE:
        return SuccessorPlan(
            boolean_identification_successor(current_course, source_root),
            SAME_GRADE_TRANSITION)
    if current_course.version == BOOLEAN_IDENTIFICATION_RELEASE:
        successor, _ = numeric_successor(current_course)
        return SuccessorPlan(successor, GRAPH_GROWTH_TRANSITION)
    if current_course.version == MINIMAL_BOOLEAN_RELEASE:
        successor, _ = numeric_successor(current_course)
        return SuccessorPlan(successor, GRAPH_GROWTH_TRANSITION)
    return None
