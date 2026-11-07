"""Immutable correction and revalidation evidence contracts."""
from __future__ import annotations

from dataclasses import dataclass

from ..semantics.cognitive_dependencies import DependencyRef
from .atlas_revalidation_common import (
    CORRECTION_EVENT_SCHEMA,
    REVALIDATED_ARTIFACT_SCHEMA,
    REVALIDATION_FRONTIER_SCHEMA,
    STATE_TRANSITION_SCHEMA,
    _ED25519_SIGNATURE,
    _canonical_bytes,
    _digest,
    _invalid,
    _name,
    _refs_payload,
    _time,
)


@dataclass(frozen=True)
class CorrectionEvent:
    event_id: str
    dependency: DependencyRef
    source_owner: str
    source_receipt_sha256: str
    old_evidence_sha256: str
    new_evidence_sha256: str
    source_time: int
    effective_time: int
    observed_at: int
    recorded_at: int
    reason_code: str
    source_signature_hex: str
    supersedes_event_ids: tuple[str, ...] = ()
    schema_version: str = CORRECTION_EVENT_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.event_id)
                or not isinstance(self.dependency, DependencyRef)
                or not _name(self.source_owner)
                or not all(_digest(value) for value in (
                    self.source_receipt_sha256, self.old_evidence_sha256,
                    self.new_evidence_sha256))
                or not all(_time(value) for value in (
                    self.source_time, self.effective_time,
                    self.observed_at, self.recorded_at))
                or not _name(self.reason_code)
                or not isinstance(self.source_signature_hex, str)
                or not _ED25519_SIGNATURE.fullmatch(self.source_signature_hex)
                or not isinstance(self.supersedes_event_ids, tuple)
                or any(not _name(item) for item in self.supersedes_event_ids)
                or len(set(self.supersedes_event_ids)) != len(self.supersedes_event_ids)
                or self.event_id in self.supersedes_event_ids
                or tuple(sorted(self.supersedes_event_ids)) != self.supersedes_event_ids
                or self.schema_version != CORRECTION_EVENT_SCHEMA):
            _invalid("BAMF_C09_CORRECTION_EVENT_INVALID")

    def signing_bytes(self) -> bytes:
        return _canonical_bytes({
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "dependency": _refs_payload((self.dependency,))[0],
            "source_owner": self.source_owner,
            "source_receipt_sha256": self.source_receipt_sha256,
            "old_evidence_sha256": self.old_evidence_sha256,
            "new_evidence_sha256": self.new_evidence_sha256,
            "source_time": self.source_time,
            "effective_time": self.effective_time,
            "observed_at": self.observed_at,
            "recorded_at": self.recorded_at,
            "reason_code": self.reason_code,
            "supersedes_event_ids": self.supersedes_event_ids,
        })


@dataclass(frozen=True)
class RevalidatedArtifact:
    artifact_id: str
    immediate_dependencies: tuple[DependencyRef, ...]
    content_digest: str
    eligible: bool
    source_receipt_sha256: str
    correction_event_id: str
    correction_receipt_sha256: str
    source_owner: str
    source_signature_hex: str
    schema_version: str = REVALIDATED_ARTIFACT_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.artifact_id)
                or not isinstance(self.immediate_dependencies, tuple)
                or any(not isinstance(ref, DependencyRef)
                       for ref in self.immediate_dependencies)
                or self.immediate_dependencies != tuple(
                    sorted(set(self.immediate_dependencies)))
                or not _digest(self.content_digest)
                or type(self.eligible) is not bool
                or not _digest(self.source_receipt_sha256)
                or not _name(self.correction_event_id)
                or not _digest(self.correction_receipt_sha256)
                or not _name(self.source_owner)
                or not isinstance(self.source_signature_hex, str)
                or not _ED25519_SIGNATURE.fullmatch(self.source_signature_hex)
                or self.schema_version != REVALIDATED_ARTIFACT_SCHEMA):
            _invalid("BAMF_C09_REVALIDATED_ARTIFACT_INVALID")

    def signing_bytes(self) -> bytes:
        return _canonical_bytes({
            "schema_version": self.schema_version,
            "artifact_id": self.artifact_id,
            "immediate_dependencies": _refs_payload(
                self.immediate_dependencies),
            "content_digest": self.content_digest,
            "eligible": self.eligible,
            "source_receipt_sha256": self.source_receipt_sha256,
            "correction_event_id": self.correction_event_id,
            "correction_receipt_sha256": self.correction_receipt_sha256,
            "source_owner": self.source_owner,
        })


@dataclass(frozen=True)
class RevalidationFrontier:
    results: tuple[RevalidatedArtifact, ...]
    schema_version: str = REVALIDATION_FRONTIER_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.results, tuple)
                or any(not isinstance(item, RevalidatedArtifact)
                       for item in self.results)
                or self.results != tuple(
                    sorted(self.results, key=lambda item: item.artifact_id))
                or len({item.artifact_id for item in self.results})
                != len(self.results)
                or self.schema_version != REVALIDATION_FRONTIER_SCHEMA):
            _invalid("BAMF_C09_REVALIDATION_FRONTIER_INVALID")


@dataclass(frozen=True)
class StateTransition:
    artifact_id: str
    previous_content_digest: str
    new_content_digest: str
    previous_eligible: bool
    new_eligible: bool
    source_receipt_sha256: str
    correction_event_id: str
    correction_receipt_sha256: str
    source_owner: str
    source_signature_hex: str
    immediate_dependencies: tuple[DependencyRef, ...]
    changed: bool
    schema_version: str = STATE_TRANSITION_SCHEMA

    def __post_init__(self) -> None:
        actual_change = (
            self.previous_content_digest != self.new_content_digest
            or self.previous_eligible != self.new_eligible)
        if (not _name(self.artifact_id)
                or not all(_digest(value) for value in (
                    self.previous_content_digest, self.new_content_digest,
                    self.source_receipt_sha256))
                or type(self.previous_eligible) is not bool
                or type(self.new_eligible) is not bool
                or type(self.changed) is not bool
                or self.changed != actual_change
                or not _name(self.source_owner)
                or not _name(self.correction_event_id)
                or not _digest(self.correction_receipt_sha256)
                or not isinstance(self.source_signature_hex, str)
                or not _ED25519_SIGNATURE.fullmatch(self.source_signature_hex)
                or not isinstance(self.immediate_dependencies, tuple)
                or self.immediate_dependencies != tuple(
                    sorted(set(self.immediate_dependencies)))
                or self.schema_version != STATE_TRANSITION_SCHEMA):
            _invalid("BAMF_C09_STATE_TRANSITION_INVALID")

    def revalidated_signing_bytes(self) -> bytes:
        return _canonical_bytes({
            "schema_version": REVALIDATED_ARTIFACT_SCHEMA,
            "artifact_id": self.artifact_id,
            "immediate_dependencies": _refs_payload(
                self.immediate_dependencies),
            "content_digest": self.new_content_digest,
            "eligible": self.new_eligible,
            "source_receipt_sha256": self.source_receipt_sha256,
            "correction_event_id": self.correction_event_id,
            "correction_receipt_sha256": self.correction_receipt_sha256,
            "source_owner": self.source_owner,
        })
