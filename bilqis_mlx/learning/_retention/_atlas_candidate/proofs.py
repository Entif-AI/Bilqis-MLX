"""Versioned optimizer-step custody proofs."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from .common import (LEGACY_STEP_PROOF_SCHEMA, STEP_PROOF_SCHEMA, invalid, is_digest)

_LEGACY_FIELDS = ("step_index", "provenance_sha256", "participation_sha256",
                  "mask_sha256", "parameter_names", "loss_bearing", "schema_version")
_V2_FIELDS = _LEGACY_FIELDS[:-1] + ("source_release_sha256",
    "training_batch_sha256", "target_capability_id", "training_authority_sha256",
    "schema_version")

@dataclass(frozen=True)
class CandidateStepProof:
    """Owner-bound proof of one executed optimizer step.

    The proof records digests of the owner-issued execution provenance and its
    derived participation and mask. It never stores a caller mask mapping.
    """

    step_index: int
    provenance_sha256: str
    participation_sha256: str
    mask_sha256: str
    parameter_names: tuple[str, ...]
    loss_bearing: bool
    source_release_sha256: str | None = None
    training_batch_sha256: str | None = None
    target_capability_id: str | None = None
    training_authority_sha256: str | None = None
    schema_version: str = STEP_PROOF_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.step_index) is not int or self.step_index < 1
                or not is_digest(self.provenance_sha256)
                or not is_digest(self.participation_sha256)
                or not is_digest(self.mask_sha256)
                or type(self.parameter_names) is not tuple
                or self.parameter_names != tuple(sorted(set(self.parameter_names)))
                or any(not isinstance(name, str) or not name
                       for name in self.parameter_names)
                or type(self.loss_bearing) is not bool
                or self.schema_version not in (
                    LEGACY_STEP_PROOF_SCHEMA, STEP_PROOF_SCHEMA)):
            invalid()
        authority = (
            self.source_release_sha256, self.training_batch_sha256,
            self.target_capability_id, self.training_authority_sha256)
        if self.schema_version == LEGACY_STEP_PROOF_SCHEMA:
            if authority != (None, None, None, None):
                invalid()
        elif (not is_digest(self.source_release_sha256)
                or not is_digest(self.training_batch_sha256)
                or not isinstance(self.target_capability_id, str)
                or not self.target_capability_id
                or not is_digest(self.training_authority_sha256)):
            invalid()

    @property
    def digest(self) -> str:
        """Content identity of one owner-bound step proof."""
        payload = json.dumps(self._payload(), sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _payload(self) -> dict:
        names = (_LEGACY_FIELDS if self.schema_version == LEGACY_STEP_PROOF_SCHEMA
                 else _V2_FIELDS)
        return {name: getattr(self, name) for name in names}

    def to_record(self) -> dict:
        """Durable custody record of one owner-bound step proof."""
        record = self._payload()
        record["proof_sha256"] = self.digest
        return record

    @classmethod
    def from_record(cls, record) -> "CandidateStepProof":
        schema = record.get("schema_version") if isinstance(record, dict) else None
        names = (_LEGACY_FIELDS if schema == LEGACY_STEP_PROOF_SCHEMA else _V2_FIELDS)
        if (not isinstance(record, dict)
                or set(record) != set(names) | {"proof_sha256"}):
            invalid()
        proof = cls(**{name: (tuple(record[name])
                              if name == "parameter_names" else record[name])
                          for name in names})
        if record["proof_sha256"] != proof.digest:
            invalid()
        return proof
