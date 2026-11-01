"""A09.1b qualified event reconciliation for immutable curriculum snapshots."""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
import hashlib

from .atlas_frontier_contracts import (
    CurriculumSnapshot, PlannerBudget, _bytes, _evidence_key, _fail,
)
from .model import LearningEvidence

_SHA_ZERO = "0" * 64


class _Event:
    def expected_digest(self) -> str:
        return hashlib.sha256(_bytes({
            field.name: getattr(self, field.name)
            for field in fields(self) if field.name != "event_sha256"
        })).hexdigest()

    def verify(self) -> None:
        if self.event_sha256 != self.expected_digest():
            _fail("BAMF_PLANNER_EVENT_DIGEST_MISMATCH")


@dataclass(frozen=True)
class SourceReleaseEvent(_Event):
    predecessor_sha256: str
    generation: int
    source_provenance_sha256: str
    successor_source: CurriculumSnapshot
    accepted: bool
    event_sha256: str
    schema: str = "bilqis.factory-source-release-event/v1"


@dataclass(frozen=True)
class LearningEvidenceEvent(_Event):
    predecessor_sha256: str
    generation: int
    source_provenance_sha256: str
    evidence: tuple[LearningEvidence, ...]
    mastery_debt: tuple[str, ...]
    debt_source_sha256: str | None
    qualification_epoch: int
    accepted: bool
    event_sha256: str
    schema: str = "bilqis.factory-learning-evidence-event/v1"


@dataclass(frozen=True)
class CorrectionEvent(_Event):
    predecessor_sha256: str
    generation: int
    source_provenance_sha256: str
    correction_generation: int
    invalidated_ready_candidate_ids: tuple[str, ...]
    invalidated_exposed_capability_ids: tuple[str, ...]
    invalidated_qualified_capability_ids: tuple[str, ...]
    invalidated_evidence: tuple[LearningEvidence, ...]
    accepted: bool
    event_sha256: str
    schema: str = "bilqis.factory-correction-event/v1"


@dataclass(frozen=True)
class FactoryAdmissionEvent(_Event):
    predecessor_sha256: str
    generation: int
    source_provenance_sha256: str
    factory_release_sha256: str
    admission_receipt_sha256: str
    accepted: bool
    event_sha256: str
    schema: str = "bilqis.factory-admission-event/v1"


@dataclass(frozen=True)
class PlannerPolicyEvent(_Event):
    predecessor_sha256: str
    generation: int
    source_provenance_sha256: str
    policy_epoch: int
    teacher_epoch: int
    budget: PlannerBudget
    accepted: bool
    event_sha256: str
    schema: str = "bilqis.factory-planner-policy-event/v1"


QualifiedPlannerEvent = (
    SourceReleaseEvent | LearningEvidenceEvent | CorrectionEvent
    | FactoryAdmissionEvent | PlannerPolicyEvent
)


def _digest(value: str) -> bool:
    return (type(value) is str and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _validate_common(snapshot: CurriculumSnapshot, event: QualifiedPlannerEvent) -> None:
    if type(snapshot) is not CurriculumSnapshot:
        _fail("BAMF_PLANNER_SNAPSHOT_INPUT_INVALID")
    snapshot.verify()
    if not isinstance(event, _Event):
        _fail("BAMF_PLANNER_EVENT_TYPE_INVALID")
    event.verify()
    expected_schema = {
        SourceReleaseEvent: "bilqis.factory-source-release-event/v1",
        LearningEvidenceEvent: "bilqis.factory-learning-evidence-event/v1",
        CorrectionEvent: "bilqis.factory-correction-event/v1",
        FactoryAdmissionEvent: "bilqis.factory-admission-event/v1",
        PlannerPolicyEvent: "bilqis.factory-planner-policy-event/v1",
    }.get(type(event))
    if (not _digest(event.predecessor_sha256)
            or not _digest(event.source_provenance_sha256)
            or type(event.generation) is not int or event.generation < 1
            or type(event.accepted) is not bool
            or event.schema != expected_schema):
        _fail("BAMF_PLANNER_EVENT_IDENTITY_INVALID")
    if (not isinstance(event, SourceReleaseEvent)
            and event.source_provenance_sha256 != snapshot.source_coverage_sha256):
        _fail("BAMF_PLANNER_EVENT_SOURCE_PROVENANCE_MISMATCH")


def _already_applied(snapshot: CurriculumSnapshot, event: QualifiedPlannerEvent) -> bool:
    if (snapshot.predecessor_sha256 != event.predecessor_sha256
            or snapshot.event_generation != event.generation):
        return False
    if isinstance(event, SourceReleaseEvent):
        source = event.successor_source
        names = (
            "semantic_release", "atlas_bundle_id", "source_bundle_id",
            "source_coverage_sha256", "frozen_census_sha256",
            "source_eligible_concept_ids", "required_source_family_ids",
            "coverage_rows", "source_held_rows", "source_ir_only_rows",
            "pending_nonconcept_rows", "prerequisite_edges", "rights_epoch",
        )
        return all(getattr(snapshot, name) == getattr(source, name) for name in names)
    if isinstance(event, LearningEvidenceEvent):
        return (set(event.evidence) <= set(snapshot.retained_evidence)
                and set(event.mastery_debt) <= set(snapshot.retained_mastery_debt)
                and event.qualification_epoch == snapshot.qualification_epoch)
    if isinstance(event, CorrectionEvent):
        return (event.correction_generation == snapshot.correction_generation
                and not set(event.invalidated_ready_candidate_ids)
                & set(snapshot.ready_candidate_ids)
                and not set(event.invalidated_exposed_capability_ids)
                & set(snapshot.unverified_exposed_capability_ids)
                and not set(event.invalidated_qualified_capability_ids)
                & set(snapshot.unverified_qualified_capability_ids)
                and not set(event.invalidated_evidence) & set(snapshot.retained_evidence))
    if isinstance(event, FactoryAdmissionEvent):
        return (snapshot.admitted_factory_release_sha256 == event.factory_release_sha256
                and snapshot.admission_receipt_sha256 == event.admission_receipt_sha256)
    if isinstance(event, PlannerPolicyEvent):
        return (snapshot.policy_epoch == event.policy_epoch
                and snapshot.teacher_epoch == event.teacher_epoch
                and snapshot.budget == event.budget)
    return False


def _successor(
    snapshot: CurriculumSnapshot, event: QualifiedPlannerEvent, **changes,
) -> CurriculumSnapshot:
    draft = replace(
        snapshot, predecessor_sha256=snapshot.snapshot_sha256,
        event_generation=event.generation, snapshot_sha256=_SHA_ZERO, **changes)
    result = replace(draft, snapshot_sha256=draft.expected_digest())
    result.verify()
    return result


def _source_changes(snapshot: CurriculumSnapshot, event: SourceReleaseEvent) -> dict:
    source = event.successor_source
    source.verify()
    old_rows = {
        (row.semantic_id, row.family_id): row for row in snapshot.coverage_rows
    }
    new_rows = {
        (row.semantic_id, row.family_id): row for row in source.coverage_rows
    }
    old_coverage = set(old_rows)
    new_coverage = set(new_rows)
    if (event.source_provenance_sha256 != source.source_coverage_sha256
            or not set(snapshot.source_eligible_concept_ids)
            <= set(source.source_eligible_concept_ids)
            or not set(snapshot.required_source_family_ids)
            <= set(source.required_source_family_ids)
            or not old_coverage <= new_coverage
            or source.rights_epoch < snapshot.rights_epoch):
        _fail("BAMF_PLANNER_SOURCE_EVENT_INVALID")
    for key, prior in old_rows.items():
        successor = new_rows[key]
        if (
            successor.implementation_status != prior.implementation_status
            or successor.reason != prior.reason
            or successor.learning_state != prior.learning_state
        ):
            _fail("BAMF_PLANNER_SOURCE_EVENT_IMPLEMENTATION_AUTHORITY_VIOLATION")
    for key in new_coverage - old_coverage:
        successor = new_rows[key]
        if (
            successor.implementation_status != "IMPLEMENTATION_UNCOVERED"
            or successor.learning_state != "LEARNING_UNVERIFIED"
        ):
            _fail("BAMF_PLANNER_SOURCE_EVENT_IMPLEMENTATION_AUTHORITY_VIOLATION")
    names = (
        "semantic_release", "atlas_bundle_id", "source_bundle_id",
        "source_coverage_sha256", "frozen_census_sha256",
        "source_eligible_concept_ids", "required_source_family_ids",
        "coverage_rows", "source_held_rows", "source_ir_only_rows",
        "pending_nonconcept_rows", "prerequisite_edges", "rights_epoch",
    )
    return {name: getattr(source, name) for name in names}


def _learning_changes(snapshot: CurriculumSnapshot, event: LearningEvidenceEvent) -> dict:
    if (event.qualification_epoch < snapshot.qualification_epoch
            or any(type(item) is not LearningEvidence for item in event.evidence)
            or any(type(item) is not str or not item for item in event.mastery_debt)
            or (event.mastery_debt and not _digest(event.debt_source_sha256))):
        _fail("BAMF_PLANNER_LEARNING_EVENT_INVALID")
    evidence = tuple(sorted(
        set(snapshot.retained_evidence) | set(event.evidence), key=_evidence_key))
    debt = tuple(sorted(set(snapshot.retained_mastery_debt) | set(event.mastery_debt)))
    debt_source = event.debt_source_sha256 if event.mastery_debt else snapshot.retained_debt_source_sha256
    return {
        "retained_evidence": evidence, "retained_mastery_debt": debt,
        "retained_debt_source_sha256": debt_source,
        "qualification_epoch": event.qualification_epoch,
    }


def _correction_changes(snapshot: CurriculumSnapshot, event: CorrectionEvent) -> dict:
    if (event.correction_generation <= snapshot.correction_generation
            or any(type(item) is not LearningEvidence for item in event.invalidated_evidence)
            or any(type(item) is not str or not item for group in (
                event.invalidated_ready_candidate_ids,
                event.invalidated_exposed_capability_ids,
                event.invalidated_qualified_capability_ids) for item in group)):
        _fail("BAMF_PLANNER_CORRECTION_EVENT_INVALID")
    remove_evidence = set(event.invalidated_evidence)
    return {
        "correction_generation": event.correction_generation,
        "ready_candidate_ids": tuple(item for item in snapshot.ready_candidate_ids
                                     if item not in event.invalidated_ready_candidate_ids),
        "unverified_exposed_capability_ids": tuple(
            item for item in snapshot.unverified_exposed_capability_ids
            if item not in event.invalidated_exposed_capability_ids),
        "unverified_qualified_capability_ids": tuple(
            item for item in snapshot.unverified_qualified_capability_ids
            if item not in event.invalidated_qualified_capability_ids),
        "retained_evidence": tuple(
            item for item in snapshot.retained_evidence if item not in remove_evidence),
    }


def _admission_changes(snapshot: CurriculumSnapshot, event: FactoryAdmissionEvent) -> dict:
    if (not _digest(event.factory_release_sha256)
            or not _digest(event.admission_receipt_sha256)
            or event.factory_release_sha256 not in snapshot.staged_factory_release_sha256s):
        _fail("BAMF_PLANNER_ADMISSION_EVENT_INVALID")
    return {
        "admitted_factory_release_sha256": event.factory_release_sha256,
        "admission_receipt_sha256": event.admission_receipt_sha256,
    }


def _policy_changes(snapshot: CurriculumSnapshot, event: PlannerPolicyEvent) -> dict:
    if (event.policy_epoch < snapshot.policy_epoch
            or event.teacher_epoch < snapshot.teacher_epoch
            or type(event.budget) is not PlannerBudget):
        _fail("BAMF_PLANNER_POLICY_EVENT_INVALID")
    return {"policy_epoch": event.policy_epoch, "teacher_epoch": event.teacher_epoch,
            "budget": event.budget}


def reconcile(
    snapshot: CurriculumSnapshot, qualified_event: QualifiedPlannerEvent,
) -> CurriculumSnapshot:
    """Fold one accepted event into a new immutable snapshot, or return a fixed point."""
    _validate_common(snapshot, qualified_event)
    if not qualified_event.accepted:
        _fail("BAMF_PLANNER_EVENT_NOT_QUALIFIED")
    if _already_applied(snapshot, qualified_event):
        return snapshot
    if (qualified_event.predecessor_sha256 != snapshot.snapshot_sha256
            or qualified_event.generation != snapshot.event_generation + 1):
        _fail("BAMF_PLANNER_EVENT_PREDECESSOR_MISMATCH")
    if isinstance(qualified_event, SourceReleaseEvent):
        changes = _source_changes(snapshot, qualified_event)
    elif isinstance(qualified_event, LearningEvidenceEvent):
        changes = _learning_changes(snapshot, qualified_event)
    elif isinstance(qualified_event, CorrectionEvent):
        changes = _correction_changes(snapshot, qualified_event)
    elif isinstance(qualified_event, FactoryAdmissionEvent):
        changes = _admission_changes(snapshot, qualified_event)
    elif isinstance(qualified_event, PlannerPolicyEvent):
        changes = _policy_changes(snapshot, qualified_event)
    else:
        _fail("BAMF_PLANNER_EVENT_TYPE_INVALID")
    if all(getattr(snapshot, name) == value for name, value in changes.items()):
        return snapshot
    return _successor(snapshot, qualified_event, **changes)
