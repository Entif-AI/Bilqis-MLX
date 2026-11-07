"""Typed A02 production-admission records carried by accepted B13 custody."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields

from .records import canonical, invalid, sha

DECISION_SCHEMA = "bilqis.mlx.a02-vocabulary-admission-decision/v1"
RECEIPT_SCHEMA = "bilqis.mlx.a02-vocabulary-admission-receipt/v1"
EVENT = "BAMF_A02_VOCABULARY_ADMITTED"
_ISSUER = object()


def _hex(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


@dataclass(frozen=True)
class VocabularyAdmissionDecision:
    """Live source-admission capability for one exact parameter extension."""

    run_id: str
    generation: int
    parent_manifest_sha256: str
    parent_feature_receipt_sha256: str
    source_allocation_sha256: str
    prepared_extents_sha256: str
    active_mask_sha256: str
    registry_mirror_sha256: str
    resource_estimate_sha256: str
    candidate_identity_sha256: str
    parent_candidate_identity_sha256: str
    feature_sha256: str
    accepted: bool = True
    schema_version: str = DECISION_SCHEMA
    _issuance: object = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        digests = tuple(getattr(self, name) for name in (
            "parent_manifest_sha256", "parent_feature_receipt_sha256",
            "source_allocation_sha256", "prepared_extents_sha256",
            "active_mask_sha256", "registry_mirror_sha256",
            "resource_estimate_sha256", "candidate_identity_sha256",
            "parent_candidate_identity_sha256", "feature_sha256"))
        if (getattr(self, "_issuance", None) is not _ISSUER
                or not isinstance(self.run_id, str) or not self.run_id
                or type(self.generation) is not int or self.generation < 1
                or any(not _hex(value) for value in digests)
                or self.accepted is not True
                or self.schema_version != DECISION_SCHEMA):
            invalid("BAMF_A02_ADMISSION_DECISION_INVALID")

    @property
    def digest(self) -> str:
        return sha(canonical(self.to_record()))

    def to_record(self) -> dict:
        return {field.name: getattr(self, field.name) for field in fields(self)
                if field.name != "_issuance"}


def issue_vocabulary_admission_decision(owner_evaluation) -> VocabularyAdmissionDecision:
    """Issue live A02 authority only from the production admission owner."""
    from .vocabulary_admission import _VocabularyAdmissionEvaluation

    if type(owner_evaluation) is not _VocabularyAdmissionEvaluation:
        invalid("BAMF_A02_ADMISSION_OWNER_REQUIRED")
    owner_evaluation.__post_init__()
    decision = object.__new__(VocabularyAdmissionDecision)
    complete = {
        name: getattr(owner_evaluation, name)
        for name in (
            "run_id", "generation", "parent_manifest_sha256",
            "parent_feature_receipt_sha256", "source_allocation_sha256",
            "prepared_extents_sha256", "active_mask_sha256",
            "registry_mirror_sha256", "resource_estimate_sha256",
            "candidate_identity_sha256", "parent_candidate_identity_sha256",
            "feature_sha256")
    }
    complete.update({"accepted": True, "schema_version": DECISION_SCHEMA})
    for name, value in (*complete.items(), ("_issuance", _ISSUER)):
        object.__setattr__(decision, name, value)
    decision.__post_init__()
    return decision


def live_vocabulary_admission_decision(value) -> bool:
    return (type(value) is VocabularyAdmissionDecision
            and getattr(value, "_issuance", None) is _ISSUER)


@dataclass(frozen=True)
class A02ProductionAdmissionReceipt:
    """Derived receipt of one accepted A02 successor generation."""

    run_id: str
    generation: int
    parent_manifest_sha256: str
    successor_manifest_sha256: str
    acceptance_sha256: str
    feature_receipt_sha256: str
    decision_sha256: str
    source_allocation_sha256: str
    registry_mirror_sha256: str
    resource_estimate_sha256: str
    active_set_sha256: str
    feature_sha256: str
    semantic_bank_count: int
    transition: str = "PARAMETER_EXTENSION"
    schema_version: str = RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        digests = tuple(getattr(self, name) for name in (
            "parent_manifest_sha256", "successor_manifest_sha256",
            "acceptance_sha256", "feature_receipt_sha256", "decision_sha256",
            "source_allocation_sha256", "registry_mirror_sha256",
            "resource_estimate_sha256", "active_set_sha256", "feature_sha256"))
        if (not isinstance(self.run_id, str) or not self.run_id
                or type(self.generation) is not int or self.generation < 1
                or any(not _hex(value) for value in digests)
                or type(self.semantic_bank_count) is not int
                or self.semantic_bank_count < 1
                or self.transition != "PARAMETER_EXTENSION"
                or self.schema_version != RECEIPT_SCHEMA):
            invalid("BAMF_A02_ADMISSION_RECEIPT_INVALID")

    @property
    def digest(self) -> str:
        return sha(canonical(asdict(self)))

    def to_record(self) -> dict:
        return {**asdict(self), "receipt_sha256": self.digest}
