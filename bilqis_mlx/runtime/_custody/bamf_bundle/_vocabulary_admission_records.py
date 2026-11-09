"""Typed A02 staging evidence for a C07-owned admission boundary."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest

from .genesis.records import (
    BamfRunIdentity, initial_generation_candidate_identity_digest,
)
from .records import BamfBundleCandidate, canonical, invalid, sha

STAGING_SCHEMA = "bilqis.mlx.a02-vocabulary-staging-receipt/v1"
STAGED_EXTENSION_SCHEMA = "bilqis.mlx.a02-staged-vocabulary-extension/v1"
STAGED_EVENT = "BAMF_A02_VOCABULARY_STAGED"
_ISSUER = object()


def _hex(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _candidate_handoff_digest(candidate: BamfBundleCandidate) -> str:
    """Seal the complete staged candidate, not only its optimizer tensors."""
    custody = candidate.retained_state.custody
    return sha(canonical({
        "authority_sha256": initial_generation_candidate_identity_digest(candidate),
        "custody": None if custody is None else asdict(custody),
        "outbox": candidate.outbox,
    }))


def _has_exact_staging_receipt(
        candidate: BamfBundleCandidate,
        receipt: A02VocabularyStagingReceipt) -> bool:
    events = tuple(
        event for event in candidate.outbox
        if isinstance(event, dict) and event.get("event") == STAGED_EVENT)
    return (len(events) == 1
            and events[0].get("staging_receipt") == receipt.to_record())


@dataclass(frozen=True)
class A02VocabularyStagingReceipt:
    """Immutable evidence for one exact, unadmitted A02 successor candidate."""

    run_id: str
    generation: int
    parent_manifest_sha256: str
    parent_feature_receipt_sha256: str
    candidate_identity_sha256: str
    source_allocation_sha256: str
    plan_sha256: str
    prepared_extents_sha256: str
    active_mask_sha256: str
    registry_mirror_sha256: str
    resource_estimate_sha256: str
    active_set_sha256: str
    feature_sha256: str
    semantic_bank_count: int
    status: str = "STAGED_NOT_ADMITTED"
    schema_version: str = STAGING_SCHEMA

    def __post_init__(self) -> None:
        digests = tuple(getattr(self, name) for name in (
            "parent_manifest_sha256", "parent_feature_receipt_sha256",
            "candidate_identity_sha256", "source_allocation_sha256",
            "plan_sha256", "prepared_extents_sha256", "active_mask_sha256",
            "registry_mirror_sha256", "resource_estimate_sha256",
            "active_set_sha256", "feature_sha256"))
        if (not isinstance(self.run_id, str) or not self.run_id
                or type(self.generation) is not int or self.generation < 1
                or any(not _hex(value) for value in digests)
                or type(self.semantic_bank_count) is not int
                or self.semantic_bank_count < 1
                or self.status != "STAGED_NOT_ADMITTED"
                or self.schema_version != STAGING_SCHEMA):
            invalid("BAMF_A02_STAGING_RECEIPT_INVALID")

    @property
    def digest(self) -> str:
        return sha(canonical(asdict(self)))

    def to_record(self) -> dict:
        return {**asdict(self), "receipt_sha256": self.digest}


@dataclass(frozen=True)
class A02StagedVocabularyExtension:
    """Exact A02 candidate/evidence handoff; it carries no admission authority."""

    candidate: BamfBundleCandidate
    receipt: A02VocabularyStagingReceipt
    schema_version: str = STAGED_EXTENSION_SCHEMA
    _issuance: object = field(init=False, default=None, repr=False, compare=False)
    _candidate_seal_sha256: str | None = field(
        init=False, default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if (getattr(self, "_issuance", None) is not _ISSUER
                or type(self.candidate) is not BamfBundleCandidate
                or type(self.candidate.run_identity) is not BamfRunIdentity
                or self.candidate.run_identity.run_id != self.candidate.run_id
                or type(self.receipt) is not A02VocabularyStagingReceipt
                or self.candidate.run_id != self.receipt.run_id
                or self.candidate.generation != self.receipt.generation
                or self.candidate.parent_manifest_sha256
                != self.receipt.parent_manifest_sha256
                or self.receipt.candidate_identity_sha256
                != candidate_identity_digest(self.candidate.retained_state)
                or self.candidate.extents.digest != self.receipt.prepared_extents_sha256
                or self.candidate.extents.active_semantic_digest
                != self.receipt.active_set_sha256
                or self.candidate.extents.factor_map_digest != self.receipt.feature_sha256
                or self.candidate.extents.semantic_bank_count
                != self.receipt.semantic_bank_count
                or not _has_exact_staging_receipt(self.candidate, self.receipt)
                or dict(self.candidate.transition) != {
                    "schema": "bilqis.mlx.bamf-generation-transition/v1",
                    "kind": "PARAMETER_EXTENSION",
                    "invalidate_derived_caches": True,
                }
                or not _hex(self._candidate_seal_sha256)
                or self._candidate_seal_sha256
                != _candidate_handoff_digest(self.candidate)
                or self.schema_version != STAGED_EXTENSION_SCHEMA):
            invalid("BAMF_A02_STAGED_EXTENSION_INVALID")


def _issue_a02_staged_vocabulary_extension(
        candidate: BamfBundleCandidate,
        receipt: A02VocabularyStagingReceipt) -> A02StagedVocabularyExtension:
    """Issue one live A02 handoff after the staging owner has built both halves."""
    staged = object.__new__(A02StagedVocabularyExtension)
    object.__setattr__(staged, "candidate", candidate)
    object.__setattr__(staged, "receipt", receipt)
    object.__setattr__(staged, "schema_version", STAGED_EXTENSION_SCHEMA)
    object.__setattr__(staged, "_issuance", _ISSUER)
    object.__setattr__(staged, "_candidate_seal_sha256",
                       _candidate_handoff_digest(candidate))
    staged.__post_init__()
    return staged


def require_issued_a02_staged_vocabulary_extension(
        value) -> A02StagedVocabularyExtension:
    """Reject caller-constructed or deserialized lookalikes at the C07 boundary."""
    if (type(value) is not A02StagedVocabularyExtension
            or getattr(value, "_issuance", None) is not _ISSUER):
        invalid("BAMF_A02_STAGED_EXTENSION_INVALID")
    value.__post_init__()
    return value
