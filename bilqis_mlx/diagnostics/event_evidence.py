"""Read verified lesson-methodology receipts from committed school boundaries.

Visits are published only after the same student and native optimizer are
recoverable. Their event IDs are generation-bound in the existing atomic
outbox; no separate specimen ledger or reinterpreted historical release.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from .observations import _require_evidence_file
from .signals import (DiagnosticFinding, DiagnosticStatus, DiagnosticTarget,
                      LearningSignal, ObservationScope)
from .teaching import METHODOLOGY_VERSION


_BOUNDARIES = frozenset((
    "GRADE_A_LIVE_EXAM_COMMITTED", "SCHOOL_GRADE_B_LIVE_EXAM_COMMITTED", "SCHOOL_LIVE_EXAM_COMMITTED",
    "SCHOOL_LIVE_CANDIDATE_COMPARED",
))
_VISITS = frozenset((
    "GRADE_A_TEACHER_VISIT_COMMITTED", "SCHOOL_GRADE_B_TEACHER_VISIT_COMMITTED", "SCHOOL_TEACHER_VISIT_COMMITTED",
))
_METHODOLOGY_SIGNALS = frozenset((
    LearningSignal.DISCONNECTED_PREREQUISITES,
    LearningSignal.EXCESSIVE_INTRODUCTORY_COMPLEXITY,
))
SHA256_HEX_LENGTH: Final = 64


def _valid_visit_header(event: dict, evidence: dict | None) -> bool:
    return bool(
        event.get("event") in _VISITS and
        isinstance(evidence, dict) and
        evidence.get("schema") == METHODOLOGY_VERSION and
        evidence.get("capability") == event.get("capability") and
        isinstance(evidence.get("course_sha256"), str) and
        len(evidence["course_sha256"]) == SHA256_HEX_LENGTH and
        type(evidence.get("optimizer_batches_observed")) is int and
        type(evidence.get("delivered_examples")) is int and
        evidence["optimizer_batches_observed"] >= 0 and
        evidence["delivered_examples"] >= 0
    )


def _check_methodology_findings(event: dict, findings: object) -> None:
    valid_inventory = (
        isinstance(findings, list) and len(findings) == 2 and
        {finding.get("signal") for finding in findings if isinstance(finding, dict)} ==
        _METHODOLOGY_SIGNALS
    )
    if not valid_inventory:
        raise ValueError("DIAGNOSTIC_METHOD_SIGNAL_INVENTORY_DRIFT")
    for finding in findings:
        valid_finding = (
            finding.get("capability") == event["capability"] and
            finding.get("target") == DiagnosticTarget.CAPABILITY and
            finding.get("status") in DiagnosticStatus
        )
        if not valid_finding:
            raise ValueError("DIAGNOSTIC_METHOD_FINDING_CONTRACT_DRIFT")


def _check_visit(event: dict) -> None:
    evidence = event.get("lesson_methodology")
    if not _valid_visit_header(event, evidence):
        raise ValueError("DIAGNOSTIC_METHOD_VISIT_CONTRACT_DRIFT")
    _check_methodology_findings(event, evidence.get("findings"))


def _methodology_ledger(events: tuple[dict, ...]) -> dict[str, dict]:
    by_id = {}
    for event in events:
        if "lesson_methodology" not in event:
            continue
        identity = event.get("event_id")
        if not isinstance(identity, str) or identity in by_id:
            raise ValueError("DIAGNOSTIC_METHOD_EVENT_ID_CONFLICT")
        by_id[identity] = event
    return by_id


def _read_events(root: Path) -> tuple[dict, ...]:
    ledger = _require_evidence_file(root, root / "events.jsonl")
    return tuple(json.loads(line) for line in ledger.read_text(
        encoding="utf-8").splitlines())


def _boundary_events(events: tuple[dict, ...]):
    return (event for event in events
            if event.get("event") in _BOUNDARIES and event.get("event_id"))


def _verify_boundary_members(outbox: list[dict], generation: int) -> None:
    boundaries = [member for member in outbox if member.get("event") in _BOUNDARIES]
    if not boundaries:
        raise ValueError("DIAGNOSTIC_METHOD_BOUNDARY_OUTBOX_MISSING")
    if any(member.get("generation") != generation for member in boundaries):
        raise ValueError("DIAGNOSTIC_METHOD_BOUNDARY_OUTBOX_MISSING")


class _CommittedMethodologyIndex:
    """Index methodology receipts from generation-bound immutable outboxes."""

    def __init__(self, root: Path):
        self.root = root
        self.outboxes: dict[int, list[dict]] = {}
        self.visits: dict[str, dict] = {}

    def outbox(self, generation: int) -> list[dict]:
        if type(generation) is not int or generation < 0:
            raise ValueError("DIAGNOSTIC_METHOD_BOUNDARY_GENERATION_DRIFT")
        if generation in self.outboxes:
            return self.outboxes[generation]
        path = _require_evidence_file(
            self.root, self.root / "states" / f"{generation:07d}.json")
        state = json.loads(path.read_text(encoding="utf-8"))
        outbox = state.get("delivery_outbox")
        if not isinstance(outbox, list):
            raise ValueError("DIAGNOSTIC_METHOD_BOUNDARY_OUTBOX_MISSING")
        self._verify_outbox_integrity(state, generation, outbox)
        self.outboxes[generation] = outbox
        return outbox

    @staticmethod
    def _verify_outbox_integrity(state: dict, generation: int,
                                 outbox: list[dict]) -> None:
        from ..grade_a_trainer import _with_delivery_outbox
        regenerated = _with_delivery_outbox(state, (
            {key: value for key, value in member.items() if key != "event_id"}
            for member in outbox))["delivery_outbox"]
        if state.get("generation") != generation or regenerated != outbox:
            raise ValueError("DIAGNOSTIC_METHOD_BOUNDARY_OUTBOX_DRIFT")
        _verify_boundary_members(outbox, generation)

    def index(self, outbox: list[dict]) -> None:
        for member in outbox:
            if "lesson_methodology" not in member:
                continue
            identity = member.get("event_id")
            if not isinstance(identity, str):
                raise ValueError("DIAGNOSTIC_METHOD_EVENT_ID_CONFLICT")
            prior = self.visits.get(identity)
            if prior is not None and prior != member:
                raise ValueError("DIAGNOSTIC_METHOD_DUPLICATE_COMMITTED_VISIT")
            _check_visit(member)
            self.visits[identity] = member

    def verify_boundary(self, boundary: dict) -> None:
        outbox = self.outbox(boundary.get("generation"))
        if outbox.count(boundary) != 1:
            raise ValueError("DIAGNOSTIC_METHOD_BOUNDARY_OUTBOX_DRIFT")
        self.index(outbox)

    def index_latest(self) -> None:
        latest_path = _require_evidence_file(self.root, self.root / "state.json")
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
        if isinstance(latest.get("delivery_outbox"), list):
            self.index(self.outbox(latest.get("generation")))

    def verify_ledger(self, ledger: dict[str, dict]) -> tuple[dict, ...]:
        verified = []
        for identity, event in ledger.items():
            member = self.visits.get(identity)
            if member is None:
                raise ValueError("DIAGNOSTIC_METHOD_UNCOMMITTED_VISIT")
            if member != event:
                raise ValueError("DIAGNOSTIC_METHOD_LEDGER_OUTBOX_CONFLICT")
            verified.append(member)
        return tuple(verified)


def load_verified_lesson_methodology(run_dir: Path) -> tuple[dict, ...]:
    """Require exact event-to-outbox membership before accepting methodology.

    Older visit records without methodology remain legitimate history; they
    cannot be retroactively interpreted as having measured S4/S5.
    """
    root = Path(run_dir).resolve(strict=True)
    events = _read_events(root)
    ledger = _methodology_ledger(events)
    committed = _CommittedMethodologyIndex(root)

    # A generation-bound immutable state is the commit authority. JSONL is a
    # replayable delivery ledger and may temporarily contain a visit before the
    # later boundary member when a process stops between two fsyncs.
    # If the replayable ledger already contains a boundary, it must match the
    # same durable outbox exactly. Its absence is recoverable by outbox replay.
    for boundary in _boundary_events(events):
        committed.verify_boundary(boundary)

    # A crash may occur after one visit ledger fsync but before its boundary
    # ledger member is replayed. state.json already points to the immutable
    # committed generation in that window, so index its exact outbox as well.
    committed.index_latest()
    return committed.verify_ledger(ledger)


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
