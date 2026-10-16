"""Automatic, non-intervening S1/S2/S3 findings at real exam boundaries.

The already scored cohort is independently checked against its stored source
receipt. Earlier exams are read without loading the actual student's weights.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path
from typing import Final

from .observations import load_archived_exam_history, observe_binary_exam
from .signals import (DiagnosticFinding, DiagnosticStatus, DiagnosticTarget,
                      LearningSignal, ObservationScope, diagnose_exam,
                      diagnose_history)


VERSION: Final = "bilqis.grade-exam.learning-warnings/v1"
_OBSERVATION_ERRORS: Final = (ValueError, OSError, KeyError, TypeError, IndexError)
_EXAM_SIGNALS: Final = (
    LearningSignal.REPETITIVE_ANSWERS,
    LearningSignal.CHANCE_LEVEL_OR_LAGGING,
    LearningSignal.LACK_OF_DURABLE_GAIN,
)


def _score_targets(scores: object) -> tuple[tuple[str, DiagnosticTarget, int, int], ...]:
    if not isinstance(scores, dict):
        return ()
    capabilities = []
    grade_scores = {}
    for capability, score in sorted(scores.items()):
        if not isinstance(capability, str) or not isinstance(score, dict):
            continue
        correct, total = score.get("correct"), score.get("total")
        if type(correct) is not int or type(total) is not int:
            continue
        capabilities.append((capability, DiagnosticTarget.CAPABILITY, correct, total))
        aggregate = grade_scores.setdefault(capability.split(".", 1)[0], [0, 0])
        aggregate[0] += correct
        aggregate[1] += total
    grades = tuple((grade, DiagnosticTarget.GRADE, correct, total)
                   for grade, (correct, total) in sorted(grade_scores.items()))
    return (*capabilities, *grades)


def _unmeasured_findings(targets, cohort_refs: tuple[str, ...], note: str) -> list[dict]:
    return [asdict(DiagnosticFinding(
        signal=signal, status=DiagnosticStatus.NOT_MEASURED,
        capability=capability, target=target,
        scope=ObservationScope.SINGLE_COHORT, evidence_count=0,
        observed_correct=correct, observed_total=total,
        majority_baseline=None, source_cohorts=cohort_refs, note=note,
    )) for capability, target, correct, total in targets for signal in _EXAM_SIGNALS]


def _unmeasured_completed_exam(last_exam: dict, reason: str) -> dict:
    """Preserve a scored exam when the optional diagnostic observer cannot run."""
    cohort = last_exam.get("cohort_sha256")
    cohort_refs = (cohort,) if isinstance(cohort, str) and cohort else ()
    note = "Diagnostic observer unavailable at this scored boundary: " + reason
    return {
        "schema": VERSION,
        "assessment_cohort_sha256": cohort,
        "student_sha256": last_exam.get("student_sha256"),
        "optimizer_step": last_exam.get("optimizer_step"),
        "history_usable": False,
        "history_issue": reason,
        "findings": _unmeasured_findings(
            _score_targets(last_exam.get("scores")), cohort_refs, note),
        "active_warnings": [],
    }


def _comparable_history(root: Path, observed) -> tuple[tuple, str | None]:
    if not (root / "events.jsonl").exists():
        return (), None
    try:
        history = load_archived_exam_history(root, grade=None)
        comparable = tuple(item for item in history if item.contract == observed.contract)
        if any(item.inventory != observed.inventory for item in comparable):
            raise ValueError("DIAGNOSTIC_INVENTORY_DRIFT")
        return comparable, None
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return (), str(exc)


def _history_findings(comparable: tuple, observed) -> tuple[tuple, str | None]:
    if not comparable:
        return (), None
    try:
        return diagnose_history((*comparable, observed)), None
    except ValueError as exc:
        return (), str(exc)


def _compact_exam_findings(current: tuple, timeline: tuple) -> list[dict]:
    lasting = {(finding.target, finding.capability): finding for finding in timeline
               if finding.signal is LearningSignal.LACK_OF_DURABLE_GAIN}
    chosen = tuple(lasting.get((finding.target, finding.capability), finding)
                   if finding.signal is LearningSignal.LACK_OF_DURABLE_GAIN else finding
                   for finding in current)
    return [asdict(finding) for finding in chosen
            if finding.target in (DiagnosticTarget.CAPABILITY, DiagnosticTarget.GRADE)
            and finding.signal in _EXAM_SIGNALS]


def _active_warnings(compact: list[dict]) -> list[dict]:
    active = (DiagnosticStatus.OBSERVED_IN_COHORT,
              DiagnosticStatus.OBSERVED_LONGITUDINALLY)
    return [dict(signal=item["signal"], target=item["target"],
                 capability=item["capability"])
            for item in compact if item["status"] in active]


def summarize_completed_exam(run_dir: Path, receipt: dict, last_exam: dict) -> dict:
    """Observations only: cannot withhold lessons or change the teacher policy."""
    root = Path(run_dir)
    payload = json.loads((root / last_exam["cohort_file"]).read_text(encoding="utf-8"))
    observed = replace(observe_binary_exam(payload, last_exam), run_id=receipt["run_id"])
    current = diagnose_exam(observed)
    comparable, history_error = _comparable_history(root, observed)
    timeline, timeline_error = _history_findings(comparable, observed)
    history_error = history_error or timeline_error
    compact = _compact_exam_findings(current, timeline if history_error is None else ())
    return {
        "schema": VERSION,
        "assessment_cohort_sha256": observed.cohort_sha256,
        "student_sha256": observed.student_sha256,
        "optimizer_step": observed.optimizer_step,
        "history_usable": history_error is None,
        "history_issue": history_error,
        "findings": compact,
        "active_warnings": _active_warnings(compact),
    }


def summarize_completed_exam_safely(run_dir: Path, receipt: dict,
                                    last_exam: dict) -> dict:
    """Never let warning reconstruction veto an already source-scored exam."""
    try:
        return summarize_completed_exam(run_dir, receipt, last_exam)
    except _OBSERVATION_ERRORS as exc:
        return _unmeasured_completed_exam(last_exam, str(exc))
