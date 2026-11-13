"""Read-only C06 priority and recovery receipts; no learning or release authority."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..factory.schedule import ScheduleProgram
from ..learning.atlas_salience import RankedOptions, SalienceEvidence
from ..learning.salience_contracts import AttentionOption, _invalid
from ..learning.salience_history import (
    EventKind, SalienceEvent, SalienceHistory, SalienceWindow, _partition, completed_windows,
)
from ..learning.salience_patterns import SalienceAggregation, aggregate_salience_patterns, _event_current
from ..learning.salience_teacher import AttentionFrontier, propose_attention_options
from ..semantics.domains import contract_digest


@dataclass(frozen=True)
class PriorityOptionObservation:
    option: AttentionOption
    grade_id: str
    evidence: SalienceEvidence
    supervision_mask: tuple[bool, bool, bool]
    hold_reason: str | None


@dataclass(frozen=True)
class LessonEffect:
    anchor_receipt_sha256: str
    anchor_event_digest: str
    followup_event_digests: tuple[str, ...]
    action_status: str
    route_status: str


@dataclass(frozen=True)
class RecoveryWindowObservation:
    window: SalienceWindow
    lesson_effects: tuple[LessonEffect, ...]
    authority_status: str
    count_scope: str = field(default='CURRENT_WINDOW', init=False)
    correction_scope: str = field(default='CAPABILITY_PARTITION_PREFIX', init=False)


@dataclass(frozen=True)
class HistoricalEventObservation:
    event: SalienceEvent
    authority_status: str
    completed_window_id: str | None


@dataclass(frozen=True)
class SaliencePriorityObservation:
    roster_digest: str
    authority_snapshot_digest: str
    metric_policy_digests: tuple[str, ...]
    history_digest: str
    window_policy_digest: str
    history_events: tuple[HistoricalEventObservation, ...]
    options: tuple[PriorityOptionObservation, ...]
    ranked: RankedOptions
    recovery: tuple[RecoveryWindowObservation, ...]
    aggregation_status: str
    aggregation: SalienceAggregation | None
    teaching_permission: bool = field(default=False, init=False)
    learning_causality: str = field(default='NOT_MEASURED', init=False)
    schema_version: str = field(default='bilqis.c06.priority-observation/v1', init=False)


def _axis_status(events, before, after):
    measured = tuple(event for event in events if getattr(event, before) is not None)
    if any(getattr(event, before) != getattr(event, after) for event in measured):
        return 'CHANGED'
    return 'MEASURED_UNCHANGED' if measured else 'NOT_MEASURED'


def _lesson_effects(prefix, window):
    current_ids = {event.event_id for event in window.events}
    anchors, probes, included = {}, {}, set()
    for event in prefix:
        if event.kind in (EventKind.ACCEPTED_LESSON, EventKind.CORRECTION_APPLIED):
            anchors.setdefault(event.source_receipt_sha256, event)
            if (event.event_id in current_ids
                    and anchors[event.source_receipt_sha256].kind is EventKind.ACCEPTED_LESSON):
                included.add(event.source_receipt_sha256)
        elif event.kind is EventKind.FOLLOWUP and event.event_id in current_ids:
            anchor = anchors.get(event.linked_receipt_sha256)
            if (anchor is None or anchor.kind is not EventKind.ACCEPTED_LESSON
                    or event.observed_at <= anchor.observed_at
                    or event.structure_sha256 != anchor.structure_sha256
                    or event.defect_sha256 != anchor.defect_sha256):
                continue
            included.add(anchor.source_receipt_sha256)
            probes.setdefault(anchor.source_receipt_sha256, []).append(event)
    result = []
    for receipt, anchor in anchors.items():
        if receipt not in included:
            continue
        events = tuple(probes.get(receipt, ()))
        result.append(LessonEffect(receipt, anchor.digest(), tuple(event.digest() for event in events),
            _axis_status(events, 'before_action_sha256', 'after_action_sha256'),
            _axis_status(events, 'before_route', 'after_route')))
    return tuple(result)


def observe_salience_priority(frontier, history, program, *, aggregation_policy=None, annotations=()):
    if (not isinstance(frontier, AttentionFrontier) or not isinstance(history, SalienceHistory)
            or not isinstance(program, ScheduleProgram) or not isinstance(annotations, tuple)
            or (aggregation_policy is None and annotations)):
        _invalid('BAMF_SALIENCE_DIAGNOSTIC_INPUT_INVALID')
    # Validate historical authenticity regardless of optional pattern aggregation.
    SalienceHistory(history.policy, history.events)
    ranked = propose_attention_options(frontier, history)
    evidence = dict(frontier.evidence)
    holds = dict(ranked.held)
    options = []
    for option in frontier.options:
        membership = tuple(grade.id for grade in program.grades
                           if any(capability.id == option.context.capability_id for capability in grade.capabilities))
        if len(membership) != 1:
            _invalid('BAMF_SALIENCE_DIAGNOSTIC_ROSTER_DRIFT')
        item = evidence[option.stable_id]
        options.append(PriorityOptionObservation(option, membership[0], item,
            tuple(metric.supervised_label is not None for metric in (item.impact, item.exigency, item.novelty)),
            holds.get(option.stable_id)))
    recovery = []
    windows = completed_windows(history)
    window_by_event = {event.event_id: window.window_id for window in windows for event in window.events}
    history_events = []
    for event in history.events:
        status = ('FUTURE_OBSERVATION_HELD' if event.observed_at > frontier.snapshot.as_of
                  else 'CURRENT_SOURCE_BOUND' if _event_current(event, history, frontier.snapshot)
                  else 'HISTORICAL_CURRENTLY_HELD')
        history_events.append(HistoricalEventObservation(event, status, window_by_event.get(event.event_id)))
    current_by_event = {item.event.event_id: item.authority_status == 'CURRENT_SOURCE_BOUND'
                        for item in history_events}
    positions = {event.event_id: index for index, event in enumerate(history.events)}
    for window in windows:
        partition = _partition(window.events[0].evidence.scope)
        prefix = tuple(event for event in history.events[:positions[window.events[-1].event_id] + 1]
                       if _partition(event.evidence.scope) == partition)
        current = all(current_by_event[event.event_id] for event in prefix)
        recovery.append(RecoveryWindowObservation(window, _lesson_effects(prefix, window),
            'CURRENT_SOURCE_BOUND' if current else 'HISTORICAL_CURRENTLY_HELD'))
    aggregation = (aggregate_salience_patterns(history, aggregation_policy, annotations, frontier.snapshot)
                   if aggregation_policy is not None else None)
    return SaliencePriorityObservation(program.digest(), contract_digest(frontier.snapshot),
        tuple(sorted({item.basis.policy.digest() for item in evidence.values()})),
        contract_digest(history), history.policy.digest(), tuple(history_events), tuple(options), ranked,
        tuple(recovery), 'MEASURED' if aggregation is not None else 'NOT_MEASURED', aggregation)
