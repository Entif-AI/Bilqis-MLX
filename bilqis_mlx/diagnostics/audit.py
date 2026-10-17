"""Neural-inert diagnostic readback of existing school evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
from typing import Final

from .observations import (_require_evidence_file, distinct_checkpoint_history,
                           load_archived_exam_history, load_saved_exam)
from .event_evidence import (SHA256_HEX_LENGTH, load_verified_lesson_methodology,
                             latest_methodology_findings)
from .signals import (DiagnosticStatus, DiagnosticTarget, LearningSignal,
                      diagnose_exam, diagnose_history)


VERSION: Final = "bilqis.school.learning-diagnostic-audit/v1"


@dataclass(frozen=True)
class _AuditEvidence:
    root: Path
    before: tuple[str, ...]
    latest: object
    history: tuple
    comparable: tuple
    findings: tuple
    longitudinal: tuple
    current: tuple
    method_visits: tuple[dict, ...]
    decisions: list[dict]
    latest_decisions: dict[str, dict]
    teacher_outcomes: list[dict]
    saved: dict


def _identities(paths: tuple[Path, ...]) -> tuple[str, ...]:
    return tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in paths)


def _exam_evidence(root: Path):
    latest = load_saved_exam(root)
    history = load_archived_exam_history(root, grade=None)
    comparable = tuple(observation for observation in history
                       if observation.contract == latest.contract)
    if any(observation.inventory != latest.inventory for observation in comparable):
        raise ValueError("DIAGNOSTIC_INVENTORY_DRIFT")
    expected_latest = replace(comparable[-1], event_outbox_verified=False) if comparable else None
    if expected_latest != latest:
        raise ValueError("DIAGNOSTIC_LATEST_EXAM_NOT_IN_COMMITTED_HISTORY")
    latest = comparable[-1]
    return (latest, history, comparable, diagnose_exam(latest),
            diagnose_history(distinct_checkpoint_history(comparable)))


def _valid_teacher_decision(decision: object) -> bool:
    if not isinstance(decision, dict):
        return False
    capability = decision.get("capability")
    identity = decision.get("decision_id")
    return (isinstance(capability, str) and bool(capability) and
            isinstance(identity, str) and len(identity) == SHA256_HEX_LENGTH)


def _teacher_evidence(saved: dict, method_visits: tuple[dict, ...]):
    decisions = [event["teacher_decision"] for event in method_visits
                 if "teacher_decision" in event]
    if any(not _valid_teacher_decision(decision) for decision in decisions):
        raise ValueError("DIAGNOSTIC_TEACHER_DECISION_DRIFT")
    latest_decisions = {decision["capability"]: decision for decision in decisions}
    last_exam = saved.get("last_exam") or {}
    teacher_outcomes = last_exam.get("teacher_outcomes", [])
    if not isinstance(teacher_outcomes, list):
        raise ValueError("DIAGNOSTIC_TEACHER_OUTCOME_DRIFT")
    _verify_teacher_outcomes(saved, teacher_outcomes)
    return decisions, latest_decisions, teacher_outcomes


def _verify_teacher_outcomes(saved: dict, teacher_outcomes: list[dict]) -> None:
    if not teacher_outcomes:
        return
    exam_events = (event for event in reversed(saved.get("delivery_outbox", ()))
                   if event.get("event") in (
                       "GRADE_A_LIVE_EXAM_COMMITTED",
                       "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED", "SCHOOL_LIVE_EXAM_COMMITTED"))
    exam_event = next(exam_events, None)
    if exam_event is None or exam_event.get("teacher_outcomes") != teacher_outcomes:
        raise ValueError("DIAGNOSTIC_TEACHER_OUTCOME_DRIFT")


def _current_findings(findings, longitudinal, methodology):
    durable = {(finding.capability, finding.target): finding for finding in longitudinal
               if finding.signal is LearningSignal.LACK_OF_DURABLE_GAIN and
               finding.status is not DiagnosticStatus.NOT_MEASURED}
    method_signals = (LearningSignal.DISCONNECTED_PREREQUISITES,
                      LearningSignal.EXCESSIVE_INTRODUCTORY_COMPLEXITY)
    return tuple(
        durable.get((finding.capability, finding.target), finding)
        if finding.signal is LearningSignal.LACK_OF_DURABLE_GAIN else
        methodology.get((finding.capability, finding.signal), finding)
        if finding.target is DiagnosticTarget.CAPABILITY and
        finding.signal in method_signals else finding
        for finding in findings)


def _audit_counts(evidence: _AuditEvidence) -> dict:
    return {
        "archived_exam_count": len(evidence.history),
        "outbox_verified_exam_count": sum(
            observation.event_outbox_verified for observation in evidence.history),
        "legacy_exam_count_without_outbox": sum(
            not observation.event_outbox_verified for observation in evidence.history),
        "comparable_exam_count": len(evidence.comparable),
        "verified_methodology_visit_count": len(evidence.method_visits),
        "verified_teacher_decision_count": len(evidence.decisions),
        "unresolved_teacher_miss_count": len(evidence.saved.get("teacher_misses", ())),
        "excluded_contract_observations": len(evidence.history) - len(evidence.comparable),
    }


def _audit_findings(evidence: _AuditEvidence) -> dict:
    unmeasured = sorted({finding.signal for finding in evidence.current
                         if finding.status is DiagnosticStatus.NOT_MEASURED and
                         finding.target is DiagnosticTarget.CAPABILITY})
    return {
        "latest_exam": asdict(evidence.latest),
        "latest_findings": [asdict(finding) for finding in evidence.findings],
        "history_findings": [asdict(finding) for finding in evidence.longitudinal],
        "current_findings": [asdict(finding) for finding in evidence.current],
        "unmeasured_signals": unmeasured,
    }


def _audit_payload(evidence: _AuditEvidence) -> dict:
    return {
        "schema": VERSION, "run_dir": str(evidence.root),
        "state_sha256": evidence.before[0], "events_sha256": evidence.before[1],
        "neural_training_started_by_this_command": False,
        "source_oracles_replayed": False, "model_or_optimizer_loaded": False,
        "teacher_policy_changed": False,
        **_audit_counts(evidence),
        "latest_teacher_decisions": evidence.latest_decisions,
        "latest_teacher_outcomes": evidence.teacher_outcomes,
        "teacher_miss_exposures": dict(evidence.saved.get("teacher_miss_exposures", {})),
        **_audit_findings(evidence),
        "evidence_boundary": (
            "Binary predictions reconstructed from archived gold, complete misses and scores. "
            "Different examination cohorts are not paired learning gains; an identical "
            "fixed exam at distinct student checkpoints can measure persistence. "
            "This audit does not qualify a curriculum release or a human training resume."),
    }


def _collect_evidence(root: Path, paths: tuple[Path, ...],
                      before: tuple[str, ...]) -> _AuditEvidence:
    latest, history, comparable, findings, longitudinal = _exam_evidence(root)
    method_visits = load_verified_lesson_methodology(root)
    method = latest_methodology_findings(method_visits)
    saved = json.loads(paths[0].read_text(encoding="utf-8"))
    decisions, latest_decisions, teacher_outcomes = _teacher_evidence(
        saved, method_visits)
    current = _current_findings(findings, longitudinal, method)
    return _AuditEvidence(
        root, before, latest, history, comparable, findings, longitudinal,
        current, method_visits, decisions, latest_decisions, teacher_outcomes, saved)


def audit_saved_run(run_dir: Path) -> dict:
    """Check recorded score consistency, without replaying source or model code.

    Historical binary correct predictions can be reconstructed from complete
    gold/miss/score receipts. This is evidence readback, not fresh inference.
    A changing live pointer/ledger requires a fresh read, never an operator lock.
    """
    root = Path(run_dir).resolve(strict=True)
    paths = (root / "state.json", root / "events.jsonl")
    for path in paths:
        _require_evidence_file(root, path)
    before = _identities(paths)
    evidence = _collect_evidence(root, paths, before)
    if _identities(paths) != before:
        raise ValueError("DIAGNOSTIC_RUN_CHANGED_DURING_READ_RETRY")
    return _audit_payload(evidence)
