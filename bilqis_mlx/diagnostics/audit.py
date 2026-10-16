"""Neural-inert diagnostic readback of existing school evidence."""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
from pathlib import Path

from .observations import _require_evidence_file, load_archived_exam_history, load_saved_exam
from .event_evidence import load_verified_lesson_methodology, latest_methodology_findings
from .signals import (DiagnosticStatus, DiagnosticTarget, LearningSignal,
                      diagnose_exam, diagnose_history)


VERSION = "bilqis.school.learning-diagnostic-audit/v1"


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

    def identities():
        return tuple(hashlib.sha256(p.read_bytes()).hexdigest() for p in paths)

    before = identities()
    latest = load_saved_exam(root)
    history = load_archived_exam_history(root, grade=None)
    comparable = tuple(obs for obs in history if obs.contract == latest.contract)
    if any(obs.inventory != latest.inventory for obs in comparable):
        raise ValueError("DIAGNOSTIC_INVENTORY_DRIFT")
    if not comparable or replace(comparable[-1], event_outbox_verified=False) != latest:
        raise ValueError("DIAGNOSTIC_LATEST_EXAM_NOT_IN_COMMITTED_HISTORY")
    latest = comparable[-1]
    findings = diagnose_exam(latest)
    longitudinal = diagnose_history(comparable)
    method_visits = load_verified_lesson_methodology(root)
    method = latest_methodology_findings(method_visits)
    durable = {(f.capability, f.target): f for f in longitudinal
               if f.signal is LearningSignal.LACK_OF_DURABLE_GAIN and
               f.status is not DiagnosticStatus.NOT_MEASURED}
    current = tuple(
        durable.get((f.capability, f.target), f)
        if f.signal is LearningSignal.LACK_OF_DURABLE_GAIN else
        method.get((f.capability, f.signal), f)
        if f.target is DiagnosticTarget.CAPABILITY and f.signal in (
            LearningSignal.DISCONNECTED_PREREQUISITES,
            LearningSignal.EXCESSIVE_INTRODUCTORY_COMPLEXITY) else f
        for f in findings)
    if identities() != before:
        raise ValueError("DIAGNOSTIC_RUN_CHANGED_DURING_READ_RETRY")
    unmeasured = sorted({f.signal for f in current
                         if f.status is DiagnosticStatus.NOT_MEASURED and
                         f.target is DiagnosticTarget.CAPABILITY})
    return {
        "schema": VERSION,
        "run_dir": str(root),
        "state_sha256": before[0],
        "events_sha256": before[1],
        "neural_training_started_by_this_command": False,
        "source_oracles_replayed": False,
        "model_or_optimizer_loaded": False,
        "teacher_policy_changed": False,
        "archived_exam_count": len(history),
        "outbox_verified_exam_count": sum(obs.event_outbox_verified for obs in history),
        "legacy_exam_count_without_outbox": sum(not obs.event_outbox_verified for obs in history),
        "comparable_exam_count": len(comparable),
        "verified_methodology_visit_count": len(method_visits),
        "excluded_contract_observations": len(history) - len(comparable),
        "latest_exam": asdict(latest),
        "latest_findings": [asdict(f) for f in findings],
        "history_findings": [asdict(f) for f in longitudinal],
        "current_findings": [asdict(f) for f in current],
        "unmeasured_signals": unmeasured,
        "evidence_boundary": (
            "Binary predictions reconstructed from archived gold, complete misses and scores. "
            "Different examination cohorts are not paired learning gains; an identical "
            "fixed exam at distinct student checkpoints can measure persistence. "
            "This audit does not qualify a curriculum release or a human training resume."),
    }
