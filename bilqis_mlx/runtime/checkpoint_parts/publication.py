"""Publish durable boundaries before retiring unreferenced checkpoint artifacts."""
from __future__ import annotations

import bilqis_mlx.data_plane as _data_plane
import bilqis_mlx.learning.capability_frontier as _learning_capability_frontier
import bilqis_mlx.learning.grade_soup as _learning_grade_soup

from .journal import _record
from .bundles import _quarantine_newer_uncommitted_bundles
from .references import _mentor_epoch_references, _regression_recovery_checkpoint
from .boundary_events import _boundary_delivery_events
from .outbox import _with_delivery_outbox, _reconcile_delivery_outbox

def _publish_boundary(run_dir, record, pending, roles, *, exam_event=None):
    """Publish visits only after model and teacher are durably recoverable."""
    student_school = record["school"]
    # The scheduler may have moved B -> A for cumulative revalidation before
    # this grade-B examination's capability winners are published. Preserve
    # the *completed assessment grade* instead of the next scheduled grade.
    active_grade = (exam_event["grade"] if exam_event is not None else
                    student_school["active_grades"][student_school["grade_index"]])
    if record.get("delivery_outbox") is not None:
        if pending or roles or exam_event is not None:
            expect = _with_delivery_outbox(
                record, _boundary_delivery_events(record, pending, roles, exam_event))
            if expect["delivery_outbox"] != record["delivery_outbox"]:
                raise ValueError("HUMAN_TRAINER_OUTBOX_BOUNDARY_ARGUMENT_DRIFT")
        _reconcile_delivery_outbox(run_dir, record)
    else:
        # Old Grade A states predate immutable event publication. Keep their
        # established behavior and their source receipts byte-for-byte.
        for event in _boundary_delivery_events(record, pending, roles, exam_event):
            _record(run_dir, event)
    school = student_school
    retained = _learning_capability_frontier.pinned(record.get("capability_best", {}), school["current_student"],
                      school["champions"])
    if record.get('curriculum_parent'):
        retained |= _learning_capability_frontier.pinned({}, record['curriculum_parent'], {})
    for peak in record.get("whole_student_peaks", ()):
        retained |= _learning_capability_frontier.pinned({}, peak["checkpoint"], {})
    for source in _mentor_epoch_references(record):
        retained |= _learning_capability_frontier.pinned({}, source, {})
    retained |= _learning_capability_frontier.pinned(record.get("graduation_perfect", {}),
                       school["current_student"], school["champions"])
    abandoned = _regression_recovery_checkpoint(record)
    if abandoned is not None:
        retained |= _learning_capability_frontier.pinned({}, abandoned, {})
    for item in record.get("historical_grade_champions", {}).values():
        retained |= _learning_capability_frontier.pinned({}, item, {})
    if record.get("legacy_frontier_pending_replay"):
        retained |= _learning_capability_frontier.pinned(record.get("historical_capability_best", {}),
                           school["current_student"], school["champions"])
    _quarantine_newer_uncommitted_bundles(run_dir, retained,
                                          school["current_student"]["optimizer_step"])
    removed = _learning_capability_frontier.retire_bundles(run_dir, retained)
    if removed:
        _record(run_dir, {"event": "SCHOOL_CHECKPOINTS_RETIRED", "grade": active_grade,
                          "generation": record["generation"],
                          "count": len(removed), "protected_count": len(retained)})
    # The old frozen recipes are unique experiment evidence, not debris.
    # Do not delete either historical or new-epoch soup bytes from this fork.
    retired_soups = _learning_grade_soup.retire_stale_soups(
        run_dir, _data_plane.live_grade_soups(record))
    if retired_soups:
        _record(run_dir, {"event": "SCHOOL_OLD_GRADE_SOUPS_RETIRED",
                          "generation": record["generation"],
                          "grade": active_grade, "count": len(retired_soups)})
