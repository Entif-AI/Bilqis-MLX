"""One-time migrations for receipts predating executable factory v2."""
from __future__ import annotations

from dataclasses import asdict, replace
import json

from .live_releases import INITIAL_RELEASE


def migrate_historical_grade_a(receipt, school, live_course, manifest):
    """Archive fixed-rubric Grade-A authority and rebind to generated live A."""

    if json.dumps(asdict(school), sort_keys=True) != json.dumps(receipt.get("school"), sort_keys=True):
        raise ValueError("HISTORICAL_MIGRATION_SCHOOL_DRIFT")
    if receipt.get("historical_grade_champions") is not None:
        return None
    legacy_frontier = receipt.get("capability_best", {})
    historical_champions = dict(school.champions)
    if historical_champions:
        school = replace(
            school,
            champions={},
            stage="MAIN",
            queue=tuple(
                capability.id
                for capability in live_course.grades[0].capabilities),
            first_recovery=(),
            pending_failures=(),
        )
    school = replace(
        school,
        course_digest=live_course.digest(),
        latest_rubric_digest=None,
    )
    record = {**receipt, "school": asdict(school)}
    record["historical_capability_best"] = legacy_frontier
    record["historical_grade_champions"] = {
        key: asdict(item) for key, item in historical_champions.items()}
    record["capability_best"] = {}
    record["curriculum_mode"] = INITIAL_RELEASE
    record["legacy_frontier_pending_replay"] = bool(legacy_frontier)
    event = {
        "event": "SCHOOL_LIVE_GRADE_A_MIGRATED",
        "historical_rubric": manifest["exam_rubric_sha256"],
        "live_rubric": live_course.grades[0].assessment_sha256,
        "legacy_best_slots": len(legacy_frontier),
        "source_student_unchanged": True,
    }
    return record, school, event
