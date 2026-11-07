"""Retention-owner acceptance binding for accepted candidate generations.

Live bindings attest the C05 screen and both optimizer identities. Historical
records remain parseable but cannot become publication capabilities.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from bilqis_mlx.errors import ErrorBus, SCHOOL

from .atlas_retention_decision import CandidateRetentionDecision

LEGACY_ACCEPTANCE_SCHEMA = "bilqis.mlx.accepted-candidate-binding/v1"
ACCEPTANCE_SCHEMA = "bilqis.mlx.accepted-candidate-binding/v2"
DIGEST_HEX_LENGTH = 64
_BINDING_ISSUER = object()
_LEGACY_FIELDS = (
    "run_id", "generation", "candidate_identity_sha256", "feature_sha256",
    "optimizer_step", "retention_reason", "step_proof_sha256",
    "decision_sha256", "schema_version",
)
_BINDING_FIELDS = (
    "run_id", "generation", "candidate_identity_sha256",
    "parent_candidate_identity_sha256", "feature_sha256", "optimizer_step",
    "retention_reason", "step_proof_sha256", "decision_sha256",
    "evidence_sha256", "policy_sha256", "schema_version",
)


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _is_digest(value) -> bool:
    return (isinstance(value, str) and len(value) == DIGEST_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in value))


def _canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def candidate_identity_digest(state) -> str:
    """Digest the full candidate optimizer state, including native AdamW."""
    import numpy as np
    optimizer = state.optimizer
    parts = {}
    for group in ("parameters", "m", "v", "update_counts"):
        parts[group] = {
            name: np.asarray(value).tobytes().hex()
            for name, value in sorted(getattr(optimizer, group).items())}
    return hashlib.sha256(_canonical({
        "state": parts, "optimizer_step": state.optimizer_step})).hexdigest()


@dataclass(frozen=True)
class AcceptedCandidateBinding:
    """Live owner-issued acceptance for one exact candidate and parent."""

    run_id: str
    generation: int
    candidate_identity_sha256: str
    parent_candidate_identity_sha256: str
    feature_sha256: str
    optimizer_step: int
    retention_reason: str
    decision_sha256: str
    evidence_sha256: str
    policy_sha256: str
    step_proof_sha256: tuple = ()
    schema_version: str = ACCEPTANCE_SCHEMA
    _issuance: object = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if (getattr(self, "_issuance", None) is not _BINDING_ISSUER
                or not isinstance(self.run_id, str) or not self.run_id
                or type(self.generation) is not int or self.generation < 0
                or any(not _is_digest(value) for value in (
                    self.candidate_identity_sha256,
                    self.parent_candidate_identity_sha256, self.feature_sha256,
                    self.decision_sha256, self.evidence_sha256, self.policy_sha256))
                or type(self.optimizer_step) is not int or self.optimizer_step < 0
                or not isinstance(self.retention_reason, str) or not self.retention_reason
                or type(self.step_proof_sha256) is not tuple
                or any(not _is_digest(value) for value in self.step_proof_sha256)
                or self.schema_version != ACCEPTANCE_SCHEMA):
            _invalid()

    def _public_record(self) -> dict:
        return {name: getattr(self, name) for name in _BINDING_FIELDS}

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical(self._public_record())).hexdigest()

    def to_record(self) -> dict:
        return {**self._public_record(), "binding_sha256": self.digest}

    @classmethod
    def from_record(cls, record) -> "ParsedAcceptedCandidateBinding":
        """Validate a historical v1/v2 record without restoring live authority."""
        if not isinstance(record, dict):
            _invalid()
        names = (_LEGACY_FIELDS if record.get("schema_version") == LEGACY_ACCEPTANCE_SCHEMA
                 else _BINDING_FIELDS if record.get("schema_version") == ACCEPTANCE_SCHEMA
                 else ())
        if not names or set(record) != set(names) | {"binding_sha256"}:
            _invalid()
        if (not isinstance(record["run_id"], str) or not record["run_id"]
                or type(record["generation"]) is not int or record["generation"] < 0
                or type(record["optimizer_step"]) is not int
                or record["optimizer_step"] < 0
                or not isinstance(record["retention_reason"], str)
                or not record["retention_reason"]
                or not isinstance(record["step_proof_sha256"], (tuple, list))
                or any(not _is_digest(value) for value in record["step_proof_sha256"])
                or any(not _is_digest(record[name]) for name in (
                    "candidate_identity_sha256", "feature_sha256",
                    "decision_sha256"))):
            _invalid()
        if names == _BINDING_FIELDS and any(not _is_digest(record[name])
                                             for name in (
                    "parent_candidate_identity_sha256", "evidence_sha256",
                    "policy_sha256")):
            _invalid()
        payload = {name: record[name] for name in names}
        if record["binding_sha256"] != hashlib.sha256(_canonical(payload)).hexdigest():
            _invalid()
        payload["step_proof_sha256"] = tuple(payload["step_proof_sha256"])
        return ParsedAcceptedCandidateBinding(payload)


@dataclass(frozen=True)
class ParsedAcceptedCandidateBinding:
    """Verified custody evidence, never accepted as a live publication token."""
    fields: dict

    def __getattr__(self, name: str):
        if name in _LEGACY_FIELDS or name in _BINDING_FIELDS:
            return self.fields.get(name)
        raise AttributeError(name)

    @property
    def digest(self) -> str:
        return hashlib.sha256(_canonical(self.fields)).hexdigest()

    def to_record(self) -> dict:
        return {**self.fields, "binding_sha256": self.digest}


def mint_acceptance_binding(decision: CandidateRetentionDecision, state, *,
                            run_id: str, generation: int,
                            feature_sha256: str) -> AcceptedCandidateBinding:
    """Bind a C05-approved decision to the exact B12 optimizer state."""
    state_digest = candidate_identity_digest(state)
    if (type(decision) is not CandidateRetentionDecision or not decision.accepted
            or decision.candidate_generation != state_digest):
        _invalid()
    binding = object.__new__(AcceptedCandidateBinding)
    for name, value in (
            ("run_id", run_id), ("generation", generation),
            ("candidate_identity_sha256", state_digest),
            ("parent_candidate_identity_sha256", decision.parent_generation),
            ("feature_sha256", feature_sha256),
            ("optimizer_step", state.optimizer_step),
            ("retention_reason", decision.reason),
            ("step_proof_sha256", tuple(proof.digest for proof in state.step_proofs)),
            ("decision_sha256", decision.digest),
            ("evidence_sha256", decision.evidence_sha256),
            ("policy_sha256", decision.policy_sha256),
            ("schema_version", ACCEPTANCE_SCHEMA),
            ("_issuance", _BINDING_ISSUER)):
        object.__setattr__(binding, name, value)
    binding.__post_init__()
    return binding
