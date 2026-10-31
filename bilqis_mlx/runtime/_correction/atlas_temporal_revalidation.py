"""Structural extraction from atlas_temporal_revalidation.py; behavior preserved."""
from __future__ import annotations
from dataclasses import replace
from graphlib import CycleError, TopologicalSorter
from ..semantics.cognitive_dependencies import ArtifactNode, DependencyKind, DependencyRef
from .atlas_temporal_contracts import TemporalEvent, TemporalEventKind, TemporalProjection, TemporalStatus, _hash, _invalid, _name, _time
from .atlas_temporal_contracts import (TEMPORAL_EVENT_SCHEMA, TEMPORAL_PROJECTION_SCHEMA, TemporalEvent, TemporalEventKind, TemporalProjection, TemporalStatus, _SHA256, _digest, _hash, _invalid, _name, _names, _time)
from .atlas_stale_replay import (DERIVED_CLAIM_SCHEMA, DerivedClaim, PROCESS_FAULT_RESULT_SCHEMA, PROCESS_FAULT_SCHEMA, ProcessFault, ProcessFaultResult, REMEDIATION_RECEIPT_SCHEMA, RemediationReceipt, RemediationStatus, escalate_stale_replay)

def project_as_of(
    events: tuple[TemporalEvent, ...], *, actor_id: str, as_of: int,
) -> TemporalProjection:
    """Use only observed and effective evidence at this prefix/as-of time."""
    if (not isinstance(events, tuple)
            or any(not isinstance(item, TemporalEvent) for item in events)
            or len({item.event_id for item in events}) != len(events)
            or not _name(actor_id) or not _time(as_of)):
        _invalid("BAMF_C09_TEMPORAL_ARGUMENT_INVALID")
    by_id = {item.event_id: item for item in events}
    for item in events:
        if item.supersedes_event_id is None:
            continue
        prior = by_id.get(item.supersedes_event_id)
        if (prior is None or prior.actor_id != item.actor_id
                or item.recorded_at < prior.recorded_at):
            _invalid("BAMF_C09_TEMPORAL_SUPERSESSION_INVALID")
    try:
        tuple(TopologicalSorter({
            item.event_id: (
                (item.supersedes_event_id,)
                if item.supersedes_event_id is not None else ())
            for item in events
        }).static_order())
    except CycleError:
        _invalid("BAMF_C09_TEMPORAL_SUPERSESSION_CYCLE")
    recorded = tuple(
        item for item in events
        if item.actor_id == actor_id and item.recorded_at <= as_of)
    visible = tuple(
        item for item in recorded
        if (item.kind is TemporalEventKind.PLANNED
            or item.effective_from <= as_of)
        and (item.effective_until is None or as_of < item.effective_until))
    # Effective corrections retain their supersession edges after expiry.
    # Expiry removes a fact from view; it cannot resurrect replaced evidence.
    effective_history = tuple(item for item in recorded
        if item.kind is TemporalEventKind.PLANNED or item.effective_from <= as_of)
    superseded = {item.supersedes_event_id for item in effective_history
                  if item.supersedes_event_id is not None}
    active = tuple(sorted(
        (item for item in visible if item.event_id not in superseded),
        key=lambda item: item.event_id))
    if not active:
        status, fact = TemporalStatus.UNKNOWN, None
    elif len(active) > 1:
        status, fact = TemporalStatus.CONFLICTING_ALTERNATIVES, None
    else:
        selected = active[0]
        fact = selected.fact_digest
        if selected.kind is TemporalEventKind.PLANNED:
            status = (
                TemporalStatus.MISSING_EXPECTED_REPORT
                if selected.expected_report_by is not None
                and as_of >= selected.expected_report_by
                else TemporalStatus.PLANNED)
        elif selected.kind is TemporalEventKind.EXPLICIT_NONOCCURRENCE:
            status = TemporalStatus.EXPLICIT_NONOCCURRENCE
        elif selected.kind is TemporalEventKind.CORRECTION:
            status = TemporalStatus.CORRECTED
        else:
            status = TemporalStatus.OBSERVED
    # Only already-recorded events contribute to time boundaries. Future
    # suffixes cannot change an earlier prefix identity or leak their facts.
    boundaries = {
        time for item in recorded
        for time in (
            item.recorded_at, item.effective_from, item.effective_until,
            item.expected_report_by)
        if time is not None
    }
    active_ids = tuple(item.event_id for item in active)
    time_key = _hash({
        "actor_id": actor_id,
        "active_event_ids": active_ids,
        "known_boundaries": tuple(sorted(boundaries)),
        "boundary_bucket": sum(time <= as_of for time in boundaries),
        "status": status.value,
    })
    return TemporalProjection(
        actor_id=actor_id, as_of=as_of, status=status,
        source_event_ids=active_ids, fact_digest=fact,
        time_dependency=DependencyRef(
            DependencyKind.TIME,
            "time:asof:" + str(len(actor_id)) + ":" + actor_id + ":" + time_key),
    )

def bind_as_of_dependency(
    node: ArtifactNode, projection: TemporalProjection,
) -> ArtifactNode:
    """Replace only this actor's time boundary on an immutable derived node."""
    if (not isinstance(node, ArtifactNode)
            or not isinstance(projection, TemporalProjection)):
        _invalid("BAMF_C09_TEMPORAL_BINDING_INVALID")
    actor_prefix = (
        "time:asof:" + str(len(projection.actor_id))
        + ":" + projection.actor_id + ":")
    if not projection.time_dependency.key.startswith(actor_prefix):
        _invalid("BAMF_C09_TEMPORAL_BINDING_INVALID")
    dependencies = tuple(sorted({
        *(ref for ref in node.immediate_dependencies
          if not (ref.kind is DependencyKind.TIME
                  and ref.key.startswith(actor_prefix))),
        projection.time_dependency,
    }))
    return replace(node, immediate_dependencies=dependencies)
