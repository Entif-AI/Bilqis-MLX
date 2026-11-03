"""Retention-owner acceptance binding for one accepted candidate generation.

Publication is not acceptance. The retention owner mints this binding when it
accepts a candidate, and B13 custody verifies the binding before a generation
may be published. The binding covers the exact accepted optimizer identity, so
a caller cannot publish an unretained state and call it an accepted generation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from bilqis_mlx.errors import ErrorBus, SCHOOL

from .atlas_retention_decision import CandidateRetentionDecision

ACCEPTANCE_SCHEMA = "bilqis.mlx.accepted-candidate-binding/v1"
DIGEST_HEX_LENGTH = 64
_BINDING_ISSUER = object()
_BINDING_FIELDS = (
    "run_id", "generation", "candidate_identity_sha256", "feature_sha256",
    "optimizer_step", "retention_reason", "step_proof_sha256",
    "decision_sha256", "schema_version",
)


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _is_digest(value) -> bool:
    """One lowercase hex digest identity, expressed as a domain contract."""
    return (isinstance(value, str) and len(value) == DIGEST_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in value))


def _canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def candidate_identity_digest(state) -> str:
    """Digest of the accepted optimizer state that a binding must cover."""
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
    """The retention owner's acceptance of one candidate generation."""

    run_id: str
    generation: int
    candidate_identity_sha256: str
    feature_sha256: str
    optimizer_step: int
    retention_reason: str
    decision_sha256: str
    step_proof_sha256: tuple = ()
    schema_version: str = ACCEPTANCE_SCHEMA
    _issuance: object = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if getattr(self, "_issuance", None) is not _BINDING_ISSUER:
            _invalid()
        if (not isinstance(self.run_id, str) or not self.run_id
                or type(self.generation) is not int or self.generation < 0
                or not _is_digest(self.candidate_identity_sha256)
                or not _is_digest(self.feature_sha256)
                or type(self.optimizer_step) is not int or self.optimizer_step < 0
                or not isinstance(self.retention_reason, str)
                or not self.retention_reason
                or type(self.step_proof_sha256) is not tuple
                or any(not _is_digest(item) for item in self.step_proof_sha256)
                or not _is_digest(self.decision_sha256)
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
    def from_record(cls, record) -> "AcceptedCandidateBinding":
        if not isinstance(record, dict) or set(record) != set(_BINDING_FIELDS) | {"binding_sha256"}:
            _invalid()
        binding = object.__new__(cls)
        for name in _BINDING_FIELDS:
            value = record[name]
            object.__setattr__(binding, name,
                               tuple(value) if name == "step_proof_sha256" else value)
        object.__setattr__(binding, "_issuance", _BINDING_ISSUER)
        binding.__post_init__()
        if record["binding_sha256"] != binding.digest:
            _invalid()
        return binding


def mint_acceptance_binding(decision: CandidateRetentionDecision, state, *,
                            run_id: str, generation: int,
                            feature_sha256: str) -> AcceptedCandidateBinding:
    """Mint the retention owner's acceptance binding for one accepted candidate.

    Only an owner-issued accepted retention decision can mint this record. The
    binding covers the accepted optimizer identity, the retention reason that
    the decision owner derived, and the digests of the owner-bound step proofs
    the accepted state carries.
    """
    if type(decision) is not CandidateRetentionDecision or not decision.accepted:
        _invalid()
    binding = object.__new__(AcceptedCandidateBinding)
    for name, value in (
            ("run_id", run_id), ("generation", generation),
            ("candidate_identity_sha256", candidate_identity_digest(state)),
            ("feature_sha256", feature_sha256),
            ("optimizer_step", state.optimizer_step),
            ("retention_reason", decision.reason),
            ("step_proof_sha256", tuple(
                proof.digest for proof in state.step_proofs)),
            ("decision_sha256", decision.digest),
            ("schema_version", ACCEPTANCE_SCHEMA), ("_issuance", _BINDING_ISSUER)):
        object.__setattr__(binding, name, value)
    binding.__post_init__()
    return binding
