"""C09.3 bitemporal source projections and post-remediation fault escalation.

Only source-qualified fixture events enter these pure functions. C10 owns
durable outbox delivery and source owners retain rights/observation authority.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from graphlib import CycleError, TopologicalSorter
import hashlib
import json
import re

from ..errors import ErrorBus, SCHOOL
from ..semantics.cognitive_dependencies import (
    ArtifactNode, DependencyIndex, DependencyKind, DependencyRef,
)
from .atlas_revalidation import (
    CorrectionEvent, RequalificationLedger,
    RequalificationUpdate, RevalidationQueue, RevalidationTask,
    mark_affected_capabilities,
)


TEMPORAL_EVENT_SCHEMA = "bilqis.c09.temporal-event/v1"
TEMPORAL_PROJECTION_SCHEMA = "bilqis.c09.temporal-projection/v1"
REMEDIATION_RECEIPT_SCHEMA = "bilqis.c09.remediation-receipt/v1"
DERIVED_CLAIM_SCHEMA = "bilqis.c09.derived-claim/v1"
PROCESS_FAULT_SCHEMA = "bilqis.c09.process-fault/v1"
PROCESS_FAULT_RESULT_SCHEMA = "bilqis.c09.process-fault-result/v1"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_REVALIDATION.INVALID, reason=reason)


def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _digest(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _time(value: object) -> bool:
    return type(value) is int and value >= 0


def _names(value: object, *, sorted_names: bool = True) -> bool:
    return (isinstance(value, tuple) and bool(value)
            and all(_name(item) for item in value)
            and len(value) == len(set(value))
            and (not sorted_names or value == tuple(sorted(value))))


def _hash(value: object) -> str:
    return hashlib.sha256(
        (json.dumps(value, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    ).hexdigest()


class TemporalEventKind(str, Enum):
    PLANNED = "PLANNED"
    OBSERVED = "OBSERVED"
    EXPLICIT_NONOCCURRENCE = "EXPLICIT_NONOCCURRENCE"
    CORRECTION = "CORRECTION"


class TemporalStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    PLANNED = "PLANNED"
    MISSING_EXPECTED_REPORT = "MISSING_EXPECTED_REPORT"
    OBSERVED = "OBSERVED"
    EXPLICIT_NONOCCURRENCE = "EXPLICIT_NONOCCURRENCE"
    CORRECTED = "CORRECTED"
    CONFLICTING_ALTERNATIVES = "CONFLICTING_ALTERNATIVES"


@dataclass(frozen=True)
class TemporalEvent:
    event_id: str
    actor_id: str
    kind: TemporalEventKind
    fact_digest: str
    source_receipt_sha256: str
    source_time: int
    effective_from: int
    effective_until: int | None
    observed_at: int
    recorded_at: int
    expected_report_by: int | None = None
    supersedes_event_id: str | None = None
    schema_version: str = TEMPORAL_EVENT_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_name(item) for item in (self.event_id, self.actor_id))
                or not isinstance(self.kind, TemporalEventKind)
                or not _digest(self.fact_digest)
                or not _digest(self.source_receipt_sha256)
                or not all(_time(item) for item in (
                    self.source_time, self.effective_from,
                    self.observed_at, self.recorded_at))
                or (self.kind is not TemporalEventKind.PLANNED
                    and self.source_time > self.observed_at)
                or self.recorded_at < self.observed_at
                or (self.effective_until is not None
                    and (not _time(self.effective_until)
                         or self.effective_until <= self.effective_from))
                or (self.expected_report_by is not None
                    and (self.kind is not TemporalEventKind.PLANNED
                         or not _time(self.expected_report_by)
                         or self.expected_report_by < self.effective_from))
                or (self.supersedes_event_id is not None
                    and (not _name(self.supersedes_event_id)
                         or self.supersedes_event_id == self.event_id))
                or self.schema_version != TEMPORAL_EVENT_SCHEMA):
            _invalid("BAMF_C09_TEMPORAL_EVENT_INVALID")


@dataclass(frozen=True)
class TemporalProjection:
    actor_id: str
    as_of: int
    status: TemporalStatus
    source_event_ids: tuple[str, ...]
    fact_digest: str | None
    time_dependency: DependencyRef
    schema_version: str = TEMPORAL_PROJECTION_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.actor_id) or not _time(self.as_of)
                or not isinstance(self.status, TemporalStatus)
                or not isinstance(self.source_event_ids, tuple)
                or self.source_event_ids != tuple(
                    sorted(set(self.source_event_ids)))
                or (self.fact_digest is not None
                    and not _digest(self.fact_digest))
                or not isinstance(self.time_dependency, DependencyRef)
                or self.time_dependency.kind is not DependencyKind.TIME
                or self.schema_version != TEMPORAL_PROJECTION_SCHEMA):
            _invalid("BAMF_C09_TEMPORAL_PROJECTION_INVALID")


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
    superseded = {item.supersedes_event_id for item in visible
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
            DependencyKind.TIME, "time:asof:" + actor_id + ":" + time_key),
    )


def bind_as_of_dependency(
    node: ArtifactNode, projection: TemporalProjection,
) -> ArtifactNode:
    """Replace only this actor's time boundary on an immutable derived node."""
    if (not isinstance(node, ArtifactNode)
            or not isinstance(projection, TemporalProjection)):
        _invalid("BAMF_C09_TEMPORAL_BINDING_INVALID")
    actor_prefix = "time:asof:" + projection.actor_id + ":"
    if not projection.time_dependency.key.startswith(actor_prefix):
        _invalid("BAMF_C09_TEMPORAL_BINDING_INVALID")
    dependencies = tuple(sorted({
        *(ref for ref in node.immediate_dependencies
          if not (ref.kind is DependencyKind.TIME
                  and ref.key.startswith(actor_prefix))),
        projection.time_dependency,
    }))
    return replace(node, immediate_dependencies=dependencies)


class RemediationStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class RemediationReceipt:
    remediation_id: str
    correction_event_id: str
    correction_receipt_sha256: str
    original_source_event_id: str
    original_source_time: int
    superseded_fact_digest: str
    superseded_source_receipt_sha256: str
    affected_artifact_ids: tuple[str, ...]
    retained_generation_sha256: str
    completed_at: int
    status: RemediationStatus
    schema_version: str = REMEDIATION_RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_name(item) for item in (
                    self.remediation_id, self.correction_event_id,
                    self.original_source_event_id))
                or not all(_digest(item) for item in (
                    self.correction_receipt_sha256,
                    self.superseded_fact_digest,
                    self.superseded_source_receipt_sha256,
                    self.retained_generation_sha256))
                or not _time(self.original_source_time)
                or not _time(self.completed_at)
                or not _names(self.affected_artifact_ids)
                or not isinstance(self.status, RemediationStatus)
                or self.schema_version != REMEDIATION_RECEIPT_SCHEMA):
            _invalid("BAMF_C09_REMEDIATION_RECEIPT_INVALID")


@dataclass(frozen=True)
class DerivedClaim:
    claim_id: str
    actor_id: str
    source_event_id: str
    source_time: int
    source_receipt_sha256: str
    fact_digest: str
    observed_at: int
    derived_path: tuple[str, ...]
    schema_version: str = DERIVED_CLAIM_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_name(item) for item in (
                    self.claim_id, self.actor_id, self.source_event_id))
                or not all(_time(item) for item in (
                    self.source_time, self.observed_at))
                or self.observed_at < self.source_time
                or not all(_digest(item) for item in (
                    self.source_receipt_sha256, self.fact_digest))
                or not _names(self.derived_path, sorted_names=False)
                or self.schema_version != DERIVED_CLAIM_SCHEMA):
            _invalid("BAMF_C09_DERIVED_CLAIM_INVALID")


@dataclass(frozen=True)
class ProcessFault:
    original_source_event_id: str
    original_source_time: int
    correction_event_id: str
    correction_receipt_sha256: str
    remediation_id: str
    offending_claim_id: str
    offending_derived_path: tuple[str, ...]
    held_artifact_ids: tuple[str, ...]
    retained_generation_sha256: str
    reason_code: str = "BAMF_C09_PROPAGATION_REPAIR_FAILED"
    error_code: str = SCHOOL.BAMF_REVALIDATION.PROPAGATION_FAILURE.code
    schema_version: str = PROCESS_FAULT_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_name(item) for item in (
                    self.original_source_event_id,
                    self.correction_event_id, self.remediation_id,
                    self.offending_claim_id))
                or not _time(self.original_source_time)
                or not all(_digest(item) for item in (
                    self.correction_receipt_sha256,
                    self.retained_generation_sha256))
                or not _names(self.offending_derived_path, sorted_names=False)
                or not _names(self.held_artifact_ids)
                or self.reason_code != "BAMF_C09_PROPAGATION_REPAIR_FAILED"
                or self.error_code !=
                SCHOOL.BAMF_REVALIDATION.PROPAGATION_FAILURE.code
                or self.schema_version != PROCESS_FAULT_SCHEMA):
            _invalid("BAMF_C09_PROCESS_FAULT_INVALID")


@dataclass(frozen=True)
class ProcessFaultResult:
    fault: ProcessFault
    queue: RevalidationQueue
    requalification: RequalificationUpdate
    schema_version: str = PROCESS_FAULT_RESULT_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.fault, ProcessFault)
                or not isinstance(self.queue, RevalidationQueue)
                or not isinstance(self.requalification, RequalificationUpdate)
                or self.schema_version != PROCESS_FAULT_RESULT_SCHEMA):
            _invalid("BAMF_C09_PROCESS_FAULT_RESULT_INVALID")


def escalate_stale_replay(
    remediation: RemediationReceipt,
    claim: DerivedClaim,
    correction: CorrectionEvent,
    index: DependencyIndex,
    ledger: RequalificationLedger,
) -> ProcessFaultResult | None:
    """Escalate a repeated superseded fact only on its proven affected path."""
    if (not isinstance(remediation, RemediationReceipt)
            or not isinstance(claim, DerivedClaim)
            or not isinstance(correction, CorrectionEvent)
            or not isinstance(index, DependencyIndex)
            or not isinstance(ledger, RequalificationLedger)):
        _invalid("BAMF_C09_PROCESS_FAULT_ARGUMENT_INVALID")
    if (remediation.correction_event_id != correction.event_id
            or remediation.correction_receipt_sha256
            != correction.source_receipt_sha256):
        _invalid("BAMF_C09_PROCESS_FAULT_CORRECTION_DRIFT")
    if remediation.completed_at < correction.recorded_at:
        _invalid("BAMF_C09_REMEDIATION_BEFORE_CORRECTION")
    for index_in_path, artifact_id in enumerate(claim.derived_path):
        node = index.node(artifact_id)
        if index_in_path and DependencyRef(
                DependencyKind.ARTIFACT,
                claim.derived_path[index_in_path - 1],
        ) not in node.immediate_dependencies:
            _invalid("BAMF_C09_DERIVED_PATH_INVALID")
    if (remediation.status is not RemediationStatus.COMPLETED
            or claim.observed_at <= remediation.completed_at
            or claim.source_time != remediation.original_source_time
            or claim.source_receipt_sha256
            != remediation.superseded_source_receipt_sha256
            or claim.fact_digest != remediation.superseded_fact_digest):
        return None
    roots = set(remediation.affected_artifact_ids).intersection(
        claim.derived_path)
    if not roots:
        return None
    held = set(roots)
    frontier = list(roots)
    while frontier:
        current = frontier.pop()
        for dependent in index.direct_dependents(
                DependencyRef(DependencyKind.ARTIFACT, current)):
            if dependent.artifact_id not in held:
                held.add(dependent.artifact_id)
                frontier.append(dependent.artifact_id)
    tasks = tuple(sorted(
        (RevalidationTask(
            artifact_id=node_id,
            exigency=index.node(node_id).exigency,
            impact=index.node(node_id).impact,
            cause=correction.dependency)
         for node_id in held),
        key=lambda task: (-task.exigency, -task.impact, task.artifact_id)))
    queue = RevalidationQueue(
        correction, tasks, tuple(sorted(held)))
    fault = ProcessFault(
        original_source_event_id=remediation.original_source_event_id,
        original_source_time=remediation.original_source_time,
        correction_event_id=correction.event_id,
        correction_receipt_sha256=correction.source_receipt_sha256,
        remediation_id=remediation.remediation_id,
        offending_claim_id=claim.claim_id,
        offending_derived_path=claim.derived_path,
        held_artifact_ids=tuple(sorted(held)),
        retained_generation_sha256=remediation.retained_generation_sha256,
    )
    return ProcessFaultResult(
        fault, queue, mark_affected_capabilities(ledger, index, queue))
