"""One-time migrations for receipts predating executable factory v2."""
from __future__ import annotations

from dataclasses import asdict, replace

from .live_releases import INITIAL_RELEASE


def migrate_historical_grade_a(
        run_dir, receipt, school, live_course, historical_course, manifest):
    """Archive fixed-rubric Grade-A authority and rebind to generated live A."""
    from .. import trainer as t

    legacy_frontier = receipt.get("capability_best", {})
    t._verify_best_custody(run_dir, receipt)
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
    record = dict(receipt)
    record["historical_capability_best"] = legacy_frontier
    record["historical_grade_champions"] = {
        key: asdict(item) for key, item in historical_champions.items()}
    record["capability_best"] = {}
    record["curriculum_mode"] = INITIAL_RELEASE
    record["legacy_frontier_pending_replay"] = bool(legacy_frontier)
    receipt = t._advance(run_dir, record, school)
    t._record(run_dir, {
        "event": "SCHOOL_LIVE_GRADE_A_MIGRATED",
        "generation": receipt["generation"],
        "historical_rubric": manifest["exam_rubric_sha256"],
        "live_rubric": live_course.grades[0].assessment_sha256,
        "legacy_best_slots": len(legacy_frontier),
        "source_student_unchanged": True,
    })
    return receipt, school
