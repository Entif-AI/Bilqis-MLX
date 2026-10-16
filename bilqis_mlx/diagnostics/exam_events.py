"""Automatic, non-intervening S1/S2/S3 findings at real exam boundaries.

The already scored cohort is independently checked against its stored source
receipt. Earlier exams are read without loading the actual student's weights.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path

from .observations import load_archived_exam_history, observe_binary_exam
from .signals import (DiagnosticStatus, DiagnosticTarget, LearningSignal,
                      diagnose_exam, diagnose_history)


VERSION = "bilqis.grade-exam.learning-warnings/v1"


def summarize_completed_exam(run_dir: Path, receipt: dict, last_exam: dict) -> dict:
    """Observations only: cannot withhold lessons or change the teacher policy."""
    root = Path(run_dir)
    payload = json.loads((root / last_exam["cohort_file"]).read_text(encoding="utf-8"))
    observed = replace(observe_binary_exam(payload, last_exam), run_id=receipt["run_id"])
    current = diagnose_exam(observed)
    comparable = ()
    history_error = None
    if (root / "events.jsonl").exists():
        try:
            history = load_archived_exam_history(root, grade=None)
            comparable = tuple(o for o in history if o.contract == observed.contract)
            if any(o.inventory != observed.inventory for o in comparable):
                raise ValueError("DIAGNOSTIC_INVENTORY_DRIFT")
        except (ValueError, OSError, KeyError, TypeError) as exc:
            # Previous history's availability cannot make a source-verified
            # present-day exam a prohibited instructional intervention.
            history_error = str(exc)
    timeline = ()
    if history_error is None and comparable:
        try:
            timeline = diagnose_history((*comparable, observed))
        except ValueError as exc:
            history_error = str(exc)

    lasting = {(f.target, f.capability): f for f in timeline
               if f.signal is LearningSignal.LACK_OF_DURABLE_GAIN}
    chosen = tuple(lasting.get((f.target, f.capability), f)
                   if f.signal is LearningSignal.LACK_OF_DURABLE_GAIN else f
                   for f in current)
    # The human needs capability- and grade-level warnings, not a duplicated
    # 75-item snapshot of every whole-student finding in each event.
    compact = [asdict(f) for f in chosen if
               f.target in (DiagnosticTarget.CAPABILITY, DiagnosticTarget.GRADE) and
               f.signal in (LearningSignal.REPETITIVE_ANSWERS,
                            LearningSignal.CHANCE_LEVEL_OR_LAGGING,
                            LearningSignal.LACK_OF_DURABLE_GAIN)]
    return {
        "schema": VERSION,
        "assessment_cohort_sha256": observed.cohort_sha256,
        "student_sha256": observed.student_sha256,
        "optimizer_step": observed.optimizer_step,
        "history_usable": history_error is None,
        "history_issue": history_error,
        "findings": compact,
        "active_warnings": [dict(signal=item["signal"],
                                 target=item["target"],
                                 capability=item["capability"])
                            for item in compact if item["status"] in (
                                DiagnosticStatus.OBSERVED_IN_COHORT,
                                DiagnosticStatus.OBSERVED_LONGITUDINALLY)],
    }
