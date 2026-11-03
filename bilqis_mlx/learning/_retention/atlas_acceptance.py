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

ACCEPTANCE_SCHEMA = "bilqis.mlx.accepted-candidate-binding/v1"
_BINDING_ISSUER = object()
_BINDING_FIELDS = (
    "run_id", "generation", "candidate_identity_sha256", "feature_sha256",
    "optimizer_step", "retention_reason", "schema_version",
)


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


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
    schema_version: str = ACCEPTANCE_SCHEMA
    _issuance: object = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if getattr(self, "_issuance", None) is not _BINDING_ISSUER:
            _invalid()
        if (not isinstance(self.run_id, str) or not self.run_id
                or type(self.generation) is not int or self.generation < 0
                or not isinstance(self.candidate_identity_sha256, str)
                or len(self.candidate_identity_sha256) != 64
                or not isinstance(self.feature_sha256, str)
                or len(self.feature_sha256) != 64
                or type(self.optimizer_step) is not int or self.optimizer_step < 0
                or not isinstance(self.retention_reason, str)
                or not self.retention_reason
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
            object.__setattr__(binding, name, record[name])
        object.__setattr__(binding, "_issuance", _BINDING_ISSUER)
        binding.__post_init__()
        if record["binding_sha256"] != binding.digest:
            _invalid()
        return binding


def mint_acceptance_binding(state, *, run_id: str, generation: int,
                            feature_sha256: str,
                            retention_reason: str) -> AcceptedCandidateBinding:
    """Mint the retention owner's acceptance binding for one candidate state."""
    binding = object.__new__(AcceptedCandidateBinding)
    for name, value in (
            ("run_id", run_id), ("generation", generation),
            ("candidate_identity_sha256", candidate_identity_digest(state)),
            ("feature_sha256", feature_sha256),
            ("optimizer_step", state.optimizer_step),
            ("retention_reason", retention_reason),
            ("schema_version", ACCEPTANCE_SCHEMA), ("_issuance", _BINDING_ISSUER)):
        object.__setattr__(binding, name, value)
    binding.__post_init__()
    return binding
