"""B13 custody record for one C07-authorized Atlas parameter extension."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest

from .records import BamfBundleCandidate, CompleteStudent, canonical, invalid, sha


ATLAS_ADMISSION_SCHEMA = "bilqis.mlx.bamf-atlas-admission-binding/v1"
_ISSUER = object()
_FIELDS = (
    "run_id", "generation", "candidate_identity_sha256",
    "parent_candidate_identity_sha256", "feature_sha256", "optimizer_step",
    "lease_sha256", "source_approval_sha256", "proposal_sha256",
    "factory_release_sha256", "staging_receipt_sha256",
    "parent_feature_receipt_sha256", "schema_version",
)


def _hex(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


@dataclass(frozen=True)
class AtlasAdmissionBinding:
    """Live C07 admission capability for one exact B13 successor generation."""

    run_id: str
    generation: int
    candidate_identity_sha256: str
    parent_candidate_identity_sha256: str
    feature_sha256: str
    optimizer_step: int
    lease_sha256: str
    source_approval_sha256: str
    proposal_sha256: str
    factory_release_sha256: str
    staging_receipt_sha256: str
    parent_feature_receipt_sha256: str
    schema_version: str = ATLAS_ADMISSION_SCHEMA
    _issuance: object = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if (getattr(self, "_issuance", None) is not _ISSUER
                or not isinstance(self.run_id, str) or not self.run_id
                or type(self.generation) is not int or self.generation < 1
                or type(self.optimizer_step) is not int or self.optimizer_step < 0
                or any(not _hex(getattr(self, name)) for name in (
                    "candidate_identity_sha256", "parent_candidate_identity_sha256",
                    "feature_sha256", "lease_sha256", "source_approval_sha256",
                    "proposal_sha256", "factory_release_sha256",
                    "staging_receipt_sha256", "parent_feature_receipt_sha256"))
                or self.schema_version != ATLAS_ADMISSION_SCHEMA):
            invalid("BAMF_ATLAS_ADMISSION_BINDING_INVALID")

    def _public_record(self) -> dict:
        return {name: getattr(self, name) for name in _FIELDS}

    @property
    def digest(self) -> str:
        return sha(canonical(self._public_record()))

    def to_record(self) -> dict:
        return {**self._public_record(), "binding_sha256": self.digest}

    @classmethod
    def from_record(cls, record: Mapping) -> "ParsedAtlasAdmissionBinding":
        if (not isinstance(record, Mapping)
                or set(record) != set(_FIELDS) | {"binding_sha256"}):
            invalid("BAMF_ATLAS_ADMISSION_BINDING_INVALID")
        payload = {name: record[name] for name in _FIELDS}
        if (payload["schema_version"] != ATLAS_ADMISSION_SCHEMA
                or not isinstance(payload["run_id"], str) or not payload["run_id"]
                or type(payload["generation"]) is not int or payload["generation"] < 1
                or type(payload["optimizer_step"]) is not int
                or payload["optimizer_step"] < 0
                or any(not _hex(payload[name]) for name in (
                    "candidate_identity_sha256", "parent_candidate_identity_sha256",
                    "feature_sha256", "lease_sha256", "source_approval_sha256",
                    "proposal_sha256", "factory_release_sha256",
                    "staging_receipt_sha256", "parent_feature_receipt_sha256"))
                or record["binding_sha256"] != sha(canonical(payload))):
            invalid("BAMF_ATLAS_ADMISSION_BINDING_INVALID")
        return ParsedAtlasAdmissionBinding(payload)


@dataclass(frozen=True)
class ParsedAtlasAdmissionBinding:
    """Verified historical admission evidence; never live C07 authority."""

    fields: dict

    def __getattr__(self, name: str):
        if name in _FIELDS:
            return self.fields[name]
        raise AttributeError(name)

    @property
    def digest(self) -> str:
        return sha(canonical(self.fields))

    def to_record(self) -> dict:
        return {**self.fields, "binding_sha256": self.digest}


def _issue_atlas_admission_binding(
        candidate: BamfBundleCandidate, parent: CompleteStudent, *,
        lease_sha256: str, source_approval_sha256: str, proposal_sha256: str,
        factory_release_sha256: str, staging_receipt_sha256: str,
        parent_feature_receipt_sha256: str) -> AtlasAdmissionBinding:
    """Mint C07 authority only after its caller has replayed lease and staging proof."""
    transition = dict(candidate.transition)
    if (type(candidate) is not BamfBundleCandidate or type(parent) is not CompleteStudent
            or candidate.run_identity is None or candidate.run_identity != parent.run_identity
            or candidate.run_id != parent.run_id
            or candidate.generation != parent.generation + 1
            or candidate.retained_state.optimizer_step != parent.retained_state.optimizer_step
            or transition != {
                "schema": "bilqis.mlx.bamf-generation-transition/v1",
                "kind": "PARAMETER_EXTENSION",
                "invalidate_derived_caches": True,
            }):
        invalid("BAMF_ATLAS_ADMISSION_BINDING_INVALID")
    binding = object.__new__(AtlasAdmissionBinding)
    for name, value in (
            ("run_id", candidate.run_id), ("generation", candidate.generation),
            ("candidate_identity_sha256", candidate_identity_digest(
                candidate.retained_state)),
            ("parent_candidate_identity_sha256", candidate_identity_digest(
                parent.retained_state)),
            ("feature_sha256", candidate.extents.factor_map_digest),
            ("optimizer_step", candidate.retained_state.optimizer_step),
            ("lease_sha256", lease_sha256),
            ("source_approval_sha256", source_approval_sha256),
            ("proposal_sha256", proposal_sha256),
            ("factory_release_sha256", factory_release_sha256),
            ("staging_receipt_sha256", staging_receipt_sha256),
            ("parent_feature_receipt_sha256", parent_feature_receipt_sha256),
            ("schema_version", ATLAS_ADMISSION_SCHEMA), ("_issuance", _ISSUER)):
        object.__setattr__(binding, name, value)
    binding.__post_init__()
    return binding


def require_issued_atlas_admission_binding(value) -> AtlasAdmissionBinding:
    if type(value) is not AtlasAdmissionBinding or getattr(value, "_issuance", None) is not _ISSUER:
        invalid("BAMF_ATLAS_ADMISSION_BINDING_INVALID")
    value.__post_init__()
    return value


def require_atlas_admission_binding(
        candidate: BamfBundleCandidate, value) -> AtlasAdmissionBinding:
    """Bind one live C07 capability to the exact candidate it authorizes."""
    binding = require_issued_atlas_admission_binding(value)
    if (binding.run_id != candidate.run_id
            or binding.generation != candidate.generation
            or binding.candidate_identity_sha256
            != candidate_identity_digest(candidate.retained_state)
            or binding.feature_sha256 != candidate.extents.factor_map_digest
            or binding.optimizer_step != candidate.retained_state.optimizer_step):
        invalid("BAMF_ATLAS_ADMISSION_BINDING_DRIFT")
    return binding
