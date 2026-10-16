"""Read verified lesson-methodology receipts from committed school boundaries.

Visits are published only after the same student and native optimizer are
recoverable. Their event IDs are generation-bound in the existing atomic
outbox; no separate specimen ledger or reinterpreted historical release.
"""
from __future__ import annotations

import json
from pathlib import Path

from .observations import _require_evidence_file
from .signals import (DiagnosticFinding, DiagnosticStatus, DiagnosticTarget,
                      LearningSignal, ObservationScope)
from .teaching import METHODOLOGY_VERSION


_BOUNDARIES = frozenset((
    "GRADE_A_LIVE_EXAM_COMMITTED", "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED",
    "SCHOOL_LIVE_CANDIDATE_COMPARED",
))
_VISITS = frozenset((
    "GRADE_A_TEACHER_VISIT_COMMITTED", "SCHOOL_GRADE_B_TEACHER_VISIT_COMMITTED",
))
_METHODOLOGY_SIGNALS = frozenset((
    LearningSignal.DISCONNECTED_PREREQUISITES,
    LearningSignal.EXCESSIVE_INTRODUCTORY_COMPLEXITY,
))


def _check_visit(event):
    evidence = event.get("lesson_methodology")
    if (event.get("event") not in _VISITS or
            not isinstance(evidence, dict) or
            evidence.get("schema") != METHODOLOGY_VERSION or
            evidence.get("capability") != event.get("capability") or
            not isinstance(evidence.get("course_sha256"), str) or
            len(evidence["course_sha256"]) != 64 or
            type(evidence.get("optimizer_batches_observed")) is not int or
            type(evidence.get("delivered_examples")) is not int or
            evidence["optimizer_batches_observed"] < 0 or
            evidence["delivered_examples"] < 0):
        raise ValueError("DIAGNOSTIC_METHOD_VISIT_CONTRACT_DRIFT")
    findings = evidence.get("findings")
    if (not isinstance(findings, list) or len(findings) != 2 or
            {f.get("signal") for f in findings if isinstance(f, dict)} !=
            _METHODOLOGY_SIGNALS):
        raise ValueError("DIAGNOSTIC_METHOD_SIGNAL_INVENTORY_DRIFT")
    for finding in findings:
        if (finding.get("capability") != event["capability"] or
                finding.get("target") != DiagnosticTarget.CAPABILITY or
                finding.get("status") not in DiagnosticStatus):
            raise ValueError("DIAGNOSTIC_METHOD_FINDING_CONTRACT_DRIFT")


def load_verified_lesson_methodology(run_dir: Path) -> tuple[dict, ...]:
    """Require exact event-to-outbox membership before accepting methodology.

    Older visit records without methodology remain legitimate history; they
    cannot be retroactively interpreted as having measured S4/S5.
    """
    root = Path(run_dir).resolve(strict=True)
    events = [json.loads(line) for line in _require_evidence_file(
        root, root / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    by_id = {}
    for event in events:
        if "lesson_methodology" not in event:
            continue
        identity = event.get("event_id")
        if not isinstance(identity, str) or identity in by_id:
            raise ValueError("DIAGNOSTIC_METHOD_EVENT_ID_CONFLICT")
        by_id[identity] = event

    verified = {}
    for boundary in events:
        if boundary.get("event") not in _BOUNDARIES or not boundary.get("event_id"):
            continue  # Historical exams predate the generation outbox.
        generation = boundary.get("generation")
        if type(generation) is not int or generation < 0:
            raise ValueError("DIAGNOSTIC_METHOD_BOUNDARY_GENERATION_DRIFT")
        path = _require_evidence_file(root, root / "states" / f"{generation:07d}.json")
        state = json.loads(path.read_text(encoding="utf-8"))
        outbox = state.get("delivery_outbox")
        if not isinstance(outbox, list):
            raise ValueError("DIAGNOSTIC_METHOD_BOUNDARY_OUTBOX_MISSING")
        from ..grade_a_trainer import _with_delivery_outbox
        if (state.get("generation") != generation or
                _with_delivery_outbox(state, (
                    {key: value for key, value in member.items() if key != "event_id"}
                    for member in outbox))["delivery_outbox"] != outbox or
                outbox.count(boundary) != 1):
            raise ValueError("DIAGNOSTIC_METHOD_BOUNDARY_OUTBOX_DRIFT")
        for member in outbox:
            if "lesson_methodology" not in member:
                continue
            identity = member["event_id"]
            if identity in verified:
                raise ValueError("DIAGNOSTIC_METHOD_DUPLICATE_COMMITTED_VISIT")
            if by_id.get(identity) != member:
                raise ValueError("DIAGNOSTIC_METHOD_LEDGER_OUTBOX_CONFLICT")
            _check_visit(member)
            verified[identity] = member
    if set(verified) != set(by_id):
        raise ValueError("DIAGNOSTIC_METHOD_UNCOMMITTED_VISIT")
    return tuple(verified.values())


def latest_methodology_findings(
    visits: tuple[dict, ...],
) -> dict[tuple[str, LearningSignal], DiagnosticFinding]:
    """Treat latest actually delivered teaching as the current observation."""
    findings = {}
    for event in visits:
        for raw in event["lesson_methodology"]["findings"]:
            finding = DiagnosticFinding(
                signal=LearningSignal(raw["signal"]),
                status=DiagnosticStatus(raw["status"]),
                capability=raw["capability"],
                target=DiagnosticTarget(raw["target"]),
                scope=ObservationScope(raw["scope"]),
                evidence_count=raw["evidence_count"],
                observed_correct=raw["observed_correct"],
                observed_total=raw["observed_total"],
                majority_baseline=raw["majority_baseline"],
                source_cohorts=tuple(raw["source_cohorts"]),
                note=raw["note"],
                trajectory=tuple(tuple(row) for row in raw.get("trajectory", ())),
            )
            findings[(event["capability"], finding.signal)] = finding
    return findings
