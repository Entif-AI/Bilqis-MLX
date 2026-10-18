"""Automatic, non-intervening S1/S2/S3 findings at real exam boundaries.

The already scored cohort is independently checked against its stored source
receipt. Earlier exams are read without loading the actual student's weights.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import json
from pathlib import Path
from typing import Final

from .observations import (_receipt_lineage_id, distinct_checkpoint_history,
                           load_archived_exam_history, observe_binary_exam,
                           observe_exam)
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
        "current_observation_usable": False,
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
        history = load_archived_exam_history(root, grade=None, incremental=True)
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
        return diagnose_history(distinct_checkpoint_history((*comparable, observed))), None
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


def apply_paired_checkpoint_s3(summary: dict, *, parent_scores: dict | None,
                               current_scores: dict, parent_sha256: str,
                               current_sha256: str, parent_step: int,
                               current_step: int, cohort_sha256: str,
                               unavailable_reason: str | None = None) -> dict:
    """Measure S3 on one fresh cohort shared by parent and current checkpoints.

    Routine school questions may rotate every cycle. Retention therefore uses
    a paired checkpoint comparison on the *same newly drawn cohort* rather than
    requiring the routine cohort itself to remain fixed across cycles.
    """
    if not isinstance(summary, dict) or not isinstance(current_scores, dict):
        raise ValueError("DIAGNOSTIC_PAIRED_S3_INVALID_INPUT")
    findings = [dict(item) for item in summary.get("findings", ())]
    if summary.get("current_observation_usable", True) is False:
        parent_scores = None
        unavailable_reason = unavailable_reason or (
            "Current source-scored diagnostic observation is unavailable: " +
            str(summary.get("history_issue") or "unknown observer failure"))
    same_checkpoint = (parent_step == current_step and parent_sha256 == current_sha256)
    conflict = parent_step == current_step and parent_sha256 != current_sha256
    if conflict:
        unavailable_reason = "DIAGNOSTIC_PAIRED_S3_SAME_STEP_CHECKPOINT_CONFLICT"
        parent_scores = None

    def score_for(target: str, capability: str, scores: dict) -> tuple[int, int] | None:
        if target == DiagnosticTarget.CAPABILITY.value:
            value = scores.get(capability)
            if not isinstance(value, dict):
                return None
            return value.get("correct"), value.get("total")
        if target == DiagnosticTarget.GRADE.value:
            members = [value for name, value in scores.items()
                       if name.split(".", 1)[0] == capability]
            if not members:
                return None
            return (sum(value.get("correct", -1) for value in members),
                    sum(value.get("total", -1) for value in members))
        return None

    for finding in findings:
        if finding.get("signal") != LearningSignal.LACK_OF_DURABLE_GAIN.value:
            continue
        current = score_for(finding.get("target"), finding.get("capability"), current_scores)
        parent = (score_for(finding.get("target"), finding.get("capability"), parent_scores)
                  if isinstance(parent_scores, dict) else None)
        valid = (parent is not None and current is not None and
                 all(type(value) is int and value >= 0 for value in (*parent, *current)) and
                 parent[1] == current[1] and 0 <= parent[0] <= parent[1] and
                 0 <= current[0] <= current[1])
        if same_checkpoint:
            valid = False
            unavailable_reason = unavailable_reason or (
                "Paired S3 needs two distinct complete student checkpoints")
        if not valid:
            finding.update({
                "status": DiagnosticStatus.NOT_MEASURED.value,
                "scope": ObservationScope.SINGLE_COHORT.value,
                "evidence_count": 0,
                "observed_correct": current[0] if current else None,
                "observed_total": current[1] if current else None,
                "source_cohorts": (cohort_sha256,),
                "trajectory": (),
                "note": "Paired S3 unavailable: " + str(
                    unavailable_reason or "parent checkpoint score evidence missing"),
            })
            continue
        delta = current[0] - parent[0]
        stable_perfect = (parent[0] == parent[1] and current[0] == current[1])
        warning = current[0] < parent[0] or (delta == 0 and not stable_perfect)
        finding.update({
            "status": (DiagnosticStatus.OBSERVED_LONGITUDINALLY.value
                       if warning else DiagnosticStatus.NOT_OBSERVED.value),
            "scope": ObservationScope.FIXED_COHORT_CHECKPOINT_SERIES.value,
            "evidence_count": 2,
            "observed_correct": current[0],
            "observed_total": current[1],
            "source_cohorts": (cohort_sha256,),
            "trajectory": ((parent_step, parent[0], parent[1]),
                           (current_step, current[0], current[1])),
            "note": ("No positive retained gain versus immediate durable parent on this fresh shared cohort"
                     if warning and delta == 0 else
                     "Regression versus immediate durable parent on this fresh shared cohort"
                     if warning else
                     "Perfect performance retained across distinct checkpoints on this fresh shared cohort"
                     if stable_perfect else
                     "Positive retained gain versus immediate durable parent on this fresh shared cohort"),
        })
    updated = dict(summary)
    updated["findings"] = findings
    updated["active_warnings"] = _active_warnings(findings)
    s3_findings = [item for item in findings
                   if item.get("signal") == LearningSignal.LACK_OF_DURABLE_GAIN.value]
    s3_usable = bool(s3_findings) and all(
        item.get("status") != DiagnosticStatus.NOT_MEASURED.value
        for item in s3_findings)
    updated["s3_usable"] = s3_usable
    updated["paired_s3"] = {
        "parent_sha256": parent_sha256,
        "parent_optimizer_step": parent_step,
        "current_sha256": current_sha256,
        "current_optimizer_step": current_step,
        "cohort_sha256": cohort_sha256,
        "source_oracled_same_cohort_pair": bool(parent_scores) and not same_checkpoint,
        "s3_usable": s3_usable,
        "unavailable_reason": unavailable_reason if not parent_scores or same_checkpoint else None,
    }
    return updated


def summarize_completed_exam(run_dir: Path, receipt: dict, last_exam: dict) -> dict:
    """Observations only: cannot withhold lessons or change the teacher policy."""
    root = Path(run_dir)
    payload = json.loads((root / last_exam["cohort_file"]).read_text(encoding="utf-8"))
    observer = observe_binary_exam if all(row.get("answer_kind") == "binary"
                                         for row in payload["rows"]) else observe_exam
    observed = replace(
        observer(payload, last_exam), run_id=receipt["run_id"],
        lineage_id=_receipt_lineage_id(receipt))
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
        "current_observation_usable": True,
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
