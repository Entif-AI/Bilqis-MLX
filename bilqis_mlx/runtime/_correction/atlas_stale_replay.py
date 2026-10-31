"""Post-remediation stale replay holds only proven affected dependency paths."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..errors import SCHOOL
from ..semantics.cognitive_dependencies import DependencyIndex, DependencyKind, DependencyRef
from .atlas_revalidation import (
    CorrectionEvent, SourceAuthorityRegistry, RevalidationQueue, RevalidationTask,
)
from .atlas_requalification import (
    RequalificationLedger, RequalificationUpdate, mark_affected_capabilities,
)
from .atlas_temporal_contracts import _invalid, _name, _digest, _time, _names

REMEDIATION_RECEIPT_SCHEMA = "bilqis.c09.remediation-receipt/v2"
DERIVED_CLAIM_SCHEMA = "bilqis.c09.derived-claim/v1"
PROCESS_FAULT_SCHEMA = "bilqis.c09.process-fault/v1"
PROCESS_FAULT_RESULT_SCHEMA = "bilqis.c09.process-fault-result/v1"


class RemediationStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class RemediationReceipt:
    remediation_id: str
    correction_event_id: str
    correction_receipt_sha256: str
    original_actor_id: str
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
                    self.original_actor_id, self.original_source_event_id))
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
    authority_registry: SourceAuthorityRegistry | None = None,
) -> ProcessFaultResult | None:
    """Escalate a repeated superseded fact only on its proven affected path."""
    if (not isinstance(remediation, RemediationReceipt)
            or not isinstance(claim, DerivedClaim)
            or not isinstance(correction, CorrectionEvent)
            or not isinstance(index, DependencyIndex)
            or not isinstance(ledger, RequalificationLedger)):
        _invalid("BAMF_C09_PROCESS_FAULT_ARGUMENT_INVALID")
    if not isinstance(authority_registry, SourceAuthorityRegistry):
        _invalid("BAMF_C09_SOURCE_AUTHORITY_MISSING")
    authority_registry.verify_correction(correction)
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
            or claim.actor_id != remediation.original_actor_id
            or claim.source_time != remediation.original_source_time
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
