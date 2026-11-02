"""Read-only operator inspection of historical release successors."""
from __future__ import annotations

from .providers import (
    BOOLEAN_RELEASE, BOOLEAN_COMPOSITE_RELEASE, BOOLEAN_IDENTIFICATION_RELEASE,
    INITIAL_RELEASE, MINIMAL_BOOLEAN_RELEASE,
    boolean_successor, minimal_boolean_successor, boolean_composite_successor,
    boolean_identification_successor, numeric_successor,
)

def _successor_preflight_details(successor, *, behavior: str,
                                 capability: str | None = None) -> dict:
    details = {
        "start_behavior": behavior,
        "next_grade": successor.grades[-1].id,
        "next_grade_source_checked": successor.executable,
        "next_grade_rubric_sha256": successor.grades[-1].assessment_sha256,
        "next_grade_complete_assessment_items": sum(
            count for grade in successor.grades for _, count in grade.exam_item_counts),
    }
    if capability is not None:
        details["next_capability"] = capability
    return details


def _numeric_successor_preflight(current_course, source_root, manifest: dict) -> dict:
    from ...grade_c_preflight import qualify
    from ...live_grade_c import (
        REGISTRY_COUNTING_TARGET,
        REGISTRY_PATH,
        integer_scope,
        registry_graph,
    )
    details = {
        "start_behavior": "HUMAN_RESUME_ADMIT_NEXT_GRADE_FROM_MASTERY",
        "next_grade": "C",
        "next_grade_policy": "SOURCE_AND_CUSTODY_CHECKS",
    }
    blockers: list[str] = []
    if REGISTRY_PATH.is_symlink():
        blockers.append("NEXT_GRADE_NATIVE_REGISTRY_ARTIFACT_UNSAFE_PATH")
        return {"details": details, "blockers": blockers}
    if not REGISTRY_PATH.is_file():
        blockers.append("NEXT_GRADE_NATIVE_REGISTRY_ARTIFACT_MISSING")
        return {"details": details, "blockers": blockers}
    details["next_grade_source"] = qualify(
        source_root, manifest, previous=current_course)
    if integer_scope(registry_graph()) != REGISTRY_COUNTING_TARGET:
        blockers.append(
            "NEXT_GRADE_REQUIRES_INTEGER_MAX=" + str(REGISTRY_COUNTING_TARGET))
    successor, _ = numeric_successor(current_course)
    details["next_grade_rubric_sha256"] = successor.grades[-1].assessment_sha256
    details["next_grade_source_checked"] = successor.executable
    return {"details": details, "blockers": blockers}


def preflight_successor(current_course, source_root, manifest: dict,
                        saved: dict, *, full_grade_b: bool = False) -> dict:
    """Provider-owned, neural-inert next-release preflight for the operator CLI."""
    blockers: list[str] = []
    details: dict = {}
    if current_course.version == INITIAL_RELEASE:
        successor = (boolean_successor(current_course, source_root) if full_grade_b
                     else minimal_boolean_successor(current_course, source_root))
        details.update(_successor_preflight_details(
            successor, behavior="HUMAN_RESUME_ADMIT_NEXT_GRADE_FROM_MASTERY"))
        return {"details": details, "blockers": blockers}
    if current_course.version == BOOLEAN_RELEASE:
        successor = boolean_composite_successor(current_course, source_root)
        details.update(_successor_preflight_details(
            successor, behavior="HUMAN_RESUME_REBIND_CURRENT_GRADE",
            capability="B.COMPOSITE"))
        return {"details": details, "blockers": blockers}
    if current_course.version == BOOLEAN_COMPOSITE_RELEASE:
        successor = boolean_identification_successor(current_course, source_root)
        details.update(_successor_preflight_details(
            successor, behavior="HUMAN_RESUME_REBIND_CURRENT_GRADE",
            capability="B.IDBOOLOPS"))
        return {"details": details, "blockers": blockers}
    if current_course.version in (BOOLEAN_IDENTIFICATION_RELEASE, MINIMAL_BOOLEAN_RELEASE):
        return _numeric_successor_preflight(current_course, source_root, manifest)
    return {"details": details, "blockers": blockers}
