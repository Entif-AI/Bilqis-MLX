"""Signed append-order windows; procedure nominations confer no source authority."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

from ..runtime.operator_registry import RouteKind
from ..semantics.cognitive_dependencies import DependencyKind, DependencyRef
from ..semantics.domains import contract_digest
from .atlas_salience import SalienceEvidence, derive_salience, verify_salience_inputs
from .salience_contracts import (
    AuthoritySnapshot, Ordinal, _invalid, _name, _sha, _signature, _signing_bytes, _time,
)


class EventKind(str, Enum):
    OBSERVATION = "OBSERVATION"
    ACCEPTED_LESSON = "ACCEPTED_LESSON"
    CORRECTION_APPLIED = "CORRECTION_APPLIED"
    FOLLOWUP = "FOLLOWUP"


@dataclass(frozen=True)
class WindowPolicy:
    policy_id: str
    version: str
    metric_policy_digest: str
    semantic_release: str
    min_independent_repeats: int
    issued_at: int
    source_owner: str
    signature_hex: str
    window_size: int = field(default=20, init=False)
    schema_version: str = field(default="bilqis.c06.window-policy/v1", init=False)

    def __post_init__(self):
        if (not all(_name(v) for v in (self.policy_id, self.version, self.source_owner))
                or not all(_sha(v) for v in (self.metric_policy_digest, self.semantic_release))
                or type(self.min_independent_repeats) is not int
                or not 2 <= self.min_independent_repeats <= 20
                or not _time(self.issued_at) or not _signature(self.signature_hex)):
            _invalid("BAMF_SALIENCE_WINDOW_POLICY_INVALID")

    def signing_bytes(self):
        return _signing_bytes(self)

    def digest(self):
        return contract_digest(self)


@dataclass(frozen=True)
class SalienceEvent:
    event_id: str
    kind: EventKind
    lineage_id: str
    episode_id: str
    structure_sha256: str
    defect_sha256: str | None
    evidence: SalienceEvidence
    observed_at: int
    source_receipt_sha256: str
    linked_receipt_sha256: str | None
    before_action_sha256: str | None
    after_action_sha256: str | None
    before_route: RouteKind | None
    after_route: RouteKind | None
    defect_present: bool | None
    source_owner: str
    signature_hex: str
    schema_version: str = field(default="bilqis.c06.salience-event/v1", init=False)

    def __post_init__(self):
        if (not all(_name(v) for v in (self.event_id, self.lineage_id, self.episode_id, self.source_owner))
                or not isinstance(self.kind, EventKind) or not isinstance(self.evidence, SalienceEvidence)
                or not _time(self.observed_at) or not _signature(self.signature_hex)
                or not all(_sha(v) for v in (self.structure_sha256, self.source_receipt_sha256))
                or any(v is not None and not _sha(v) for v in (
                    self.defect_sha256, self.linked_receipt_sha256,
                    self.before_action_sha256, self.after_action_sha256))
                or (self.before_action_sha256 is None) != (self.after_action_sha256 is None)
                or (self.before_route is None) != (self.after_route is None)
                or any(v is not None and not isinstance(v, RouteKind)
                       for v in (self.before_route, self.after_route))
                or (self.defect_present is not None and type(self.defect_present) is not bool)
                or ((self.defect_present is not None or self.kind is EventKind.CORRECTION_APPLIED)
                    and self.defect_sha256 is None)
                or (self.kind is EventKind.FOLLOWUP and self.linked_receipt_sha256 is None)):
            _invalid("BAMF_SALIENCE_EVENT_INVALID")

    def signing_bytes(self):
        return _signing_bytes(self)

    def digest(self):
        return contract_digest(self)


def _partition(context):
    # Retained generations and teacher epochs can move within one capability epoch.
    return (context.capability_id, context.capability_epoch, context.scope,
            context.semantic_release, context.source_binding_digest, context.source_family_id,
            context.rights_epoch, context.correction_generation)


@dataclass(frozen=True)
class SalienceHistory:
    policy: WindowPolicy
    events: tuple[SalienceEvent, ...]

    def __post_init__(self):
        if (not isinstance(self.policy, WindowPolicy) or not isinstance(self.events, tuple)
                or any(not isinstance(event, SalienceEvent) for event in self.events)
                or len({event.event_id for event in self.events}) != len(self.events)):
            _invalid("BAMF_SALIENCE_HISTORY_INVALID")
        for event in self.events:
            _verify_event(self.policy, event, event.evidence.basis.snapshot)


def _verify_event(policy, event, snapshot):
    if not isinstance(snapshot, AuthoritySnapshot):
        _invalid("BAMF_SALIENCE_HISTORY_SNAPSHOT_MISSING")
    basis = event.evidence.basis
    if (basis.policy.digest() != policy.metric_policy_digest
            or basis.context.semantic_release != policy.semantic_release
            or policy.issued_at > event.observed_at or event.observed_at != basis.snapshot.as_of
            or event.observed_at > snapshot.as_of
            or not any(_partition(context) == _partition(basis.context) for context in snapshot.contexts)):
        _invalid("BAMF_SALIENCE_HISTORY_SCOPE_OR_TIME_DRIFT")
    verified = verify_salience_inputs(basis.facts, basis.policy, basis.snapshot, basis.context)
    verify_salience_inputs(basis.facts, basis.policy,
        AuthoritySnapshot((basis.context,), basis.snapshot.as_of, snapshot.registry), basis.context)
    if derive_salience(verified) != event.evidence:
        _invalid("BAMF_SALIENCE_HISTORY_EVIDENCE_DRIFT")
    snapshot.registry.verify_detached(policy.source_owner,
        DependencyRef(DependencyKind.POLICY, "salience-policy:" + policy.policy_id),
        policy.signature_hex, policy.signing_bytes())
    snapshot.registry.verify_detached(event.source_owner,
        DependencyRef(DependencyKind.ARTIFACT, "salience-event:" + event.event_id),
        event.signature_hex, event.signing_bytes())


def append_salience_event(history, event, authority_snapshot):
    if not isinstance(history, SalienceHistory) or not isinstance(event, SalienceEvent):
        _invalid("BAMF_SALIENCE_HISTORY_APPEND_INVALID")
    _verify_event(history.policy, event, authority_snapshot)
    previous = next((old for old in history.events if old.event_id == event.event_id), None)
    if previous is not None:
        if previous != event:
            _invalid("BAMF_SALIENCE_HISTORY_EVENT_ID_DIVERGENCE")
        return history
    return SalienceHistory(history.policy, (*history.events, event))


@dataclass(frozen=True)
class ProcedureCandidate:
    candidate_id: str
    structure_sha256: str
    defect_sha256: str
    lineage_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    independent_lineages: int
    source_gold: bool = field(default=False, init=False)
    qualified_for_teaching: bool = field(default=False, init=False)
    disposition: str = field(default="INVESTIGATION_ONLY", init=False)


@dataclass(frozen=True)
class CorrectionFollowup:
    correction_receipt_sha256: str
    followup_event_ids: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class SalienceWindow:
    window_id: str
    events: tuple[SalienceEvent, ...]
    lateness: tuple[int, ...]
    procedure_candidates: tuple[ProcedureCandidate, ...]
    accepted_lesson_count: int
    changed_actions: int
    changed_routes: int
    correction_followups: tuple[CorrectionFollowup, ...]
    schema_version: str = field(default="bilqis.c06.salience-window/v1", init=False)


def completed_windows(history: SalienceHistory):
    """Only accepted append prefixes close windows; late observations cannot reorder them."""
    if not isinstance(history, SalienceHistory):
        _invalid("BAMF_SALIENCE_HISTORY_REQUIRED")
    partitions = defaultdict(list)
    closed = []
    for position, event in enumerate(history.events):
        key = _partition(event.evidence.scope)
        partition = partitions[key]
        lag = max(0, max((item[1].observed_at for item in partition), default=0) - event.observed_at)
        partition.append((position, event, lag))
        if len(partition) % 20:
            continue
        chunk = partition[-20:]
        events = tuple(item[1] for item in chunk)
        window_id = contract_digest((history.policy.digest(), key, len(partition) // 20))
        groups = defaultdict(list)
        for item in events:
            if (item.defect_present is True and item.defect_sha256 is not None
                    and item.evidence.impact.ordinal is Ordinal.LOW
                    and item.evidence.exigency.ordinal is Ordinal.LOW):
                groups[(item.structure_sha256, item.defect_sha256)].append(item)
        candidates = []
        for (structure, defect), items in sorted(groups.items()):
            lineages = tuple(sorted({item.lineage_id for item in items}))
            if len(lineages) >= history.policy.min_independent_repeats:
                candidates.append(ProcedureCandidate(
                    contract_digest((window_id, structure, defect)), structure, defect,
                    lineages, tuple(item.event_id for item in items), len(lineages)))
        # Resolve only against earlier accepted events, never future observations.
        anchors = {}
        changed_actions = changed_routes = 0
        followups = defaultdict(list)
        for _, item, _ in partition:
            if item.kind in (EventKind.ACCEPTED_LESSON, EventKind.CORRECTION_APPLIED):
                anchors.setdefault(item.source_receipt_sha256, item)
            elif item.kind is EventKind.FOLLOWUP:
                anchor = anchors.get(item.linked_receipt_sha256)
                if (anchor is None or item.observed_at <= anchor.observed_at
                        or item.structure_sha256 != anchor.structure_sha256
                        or item.defect_sha256 != anchor.defect_sha256):
                    continue
                if anchor.kind is EventKind.ACCEPTED_LESSON and item in events:
                    changed_actions += int(item.before_action_sha256 is not None
                                           and item.before_action_sha256 != item.after_action_sha256)
                    changed_routes += int(item.before_route is not None and item.before_route != item.after_route)
                if anchor.kind is EventKind.CORRECTION_APPLIED and item.defect_present is not None:
                    followups[anchor.source_receipt_sha256].append(item)
        corrections = []
        for receipt, anchor in anchors.items():
            if anchor.kind is EventKind.CORRECTION_APPLIED:
                measured = followups[receipt]
                status = ("RECURRENCE_OBSERVED" if any(item.defect_present for item in measured)
                          else "NO_RECURRENCE_IN_MEASURED_FOLLOWUP" if measured else "NOT_MEASURED")
                corrections.append(CorrectionFollowup(receipt, tuple(item.event_id for item in measured), status))
        closed.append(SalienceWindow(window_id, events, tuple(item[2] for item in chunk), tuple(candidates),
            len({item.source_receipt_sha256 for item in events if item.kind is EventKind.ACCEPTED_LESSON}),
            changed_actions, changed_routes, tuple(corrections)))
    return tuple(closed)
