"""Versioned optimizer-step custody proofs."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from .common import (
    LEGACY_STEP_PROOF_SCHEMA, LOGICAL_BATCH_STEP_PROOF_SCHEMA,
    PREVIOUS_STEP_PROOF_SCHEMA, STEP_PROOF_SCHEMA,
    invalid, is_digest,
)

_LEGACY_FIELDS = ("step_index", "provenance_sha256", "participation_sha256",
                  "mask_sha256", "parameter_names", "loss_bearing", "schema_version")
_V2_FIELDS = _LEGACY_FIELDS[:-1] + ("source_release_sha256",
    "training_batch_sha256", "target_capability_id", "training_authority_sha256",
    "schema_version")
_V3_FIELDS = _V2_FIELDS[:-1] + (
    "source_family_id", "episode_id", "schema_version")
_V4_FIELDS = _V2_FIELDS[:-1] + (
    "training_authority_members", "schema_version")
_LOGICAL_BATCH_MIN_MEMBERS = 2
_LOGICAL_BATCH_MEMBER_WIDTH = 3


def _valid_logical_batch_member(item) -> bool:
    if type(item) is not tuple or len(item) != _LOGICAL_BATCH_MEMBER_WIDTH:
        return False
    digest, family, episode = item
    return (is_digest(digest)
            and isinstance(family, str) and bool(family)
            and isinstance(episode, str) and bool(episode))

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
    source_family_id: str | None = None
    episode_id: str | None = None
    schema_version: str = STEP_PROOF_SCHEMA
    training_authority_members: tuple[tuple[str, str, str], ...] = ()

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
                    LEGACY_STEP_PROOF_SCHEMA, PREVIOUS_STEP_PROOF_SCHEMA,
                    STEP_PROOF_SCHEMA, LOGICAL_BATCH_STEP_PROOF_SCHEMA)):
            invalid()
        authority = (
            self.source_release_sha256, self.training_batch_sha256,
            self.target_capability_id, self.training_authority_sha256)
        if self.schema_version == LEGACY_STEP_PROOF_SCHEMA:
            if (authority != (None, None, None, None)
                    or self.source_family_id is not None
                    or self.episode_id is not None
                    or self.training_authority_members):
                invalid()
        elif (not is_digest(self.source_release_sha256)
                or not is_digest(self.training_batch_sha256)
                or not isinstance(self.target_capability_id, str)
                or not self.target_capability_id
                or not is_digest(self.training_authority_sha256)):
            invalid()
        if self.schema_version == PREVIOUS_STEP_PROOF_SCHEMA:
            if (self.source_family_id is not None or self.episode_id is not None
                    or self.training_authority_members):
                invalid()
        elif self.schema_version == STEP_PROOF_SCHEMA and (
                not isinstance(self.source_family_id, str) or not self.source_family_id
                or not isinstance(self.episode_id, str) or not self.episode_id
                or self.training_authority_members):
            invalid()
        elif self.schema_version == LOGICAL_BATCH_STEP_PROOF_SCHEMA:
            if (self.source_family_id is not None or self.episode_id is not None
                    or type(self.training_authority_members) is not tuple
                    or len(self.training_authority_members) < _LOGICAL_BATCH_MIN_MEMBERS
                    or any(not _valid_logical_batch_member(item)
                           for item in self.training_authority_members)
                    or len({item[0] for item in self.training_authority_members})
                    != len(self.training_authority_members)
                    or len({item[1] for item in self.training_authority_members}) != 1):
                invalid()

    @property
    def digest(self) -> str:
        """Content identity of one owner-bound step proof."""
        payload = json.dumps(self._payload(), sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _payload(self) -> dict:
        names = (_LEGACY_FIELDS if self.schema_version == LEGACY_STEP_PROOF_SCHEMA
                 else _V2_FIELDS if self.schema_version == PREVIOUS_STEP_PROOF_SCHEMA
                 else _V3_FIELDS if self.schema_version == STEP_PROOF_SCHEMA
                 else _V4_FIELDS)
        return {name: getattr(self, name) for name in names}

    def to_record(self) -> dict:
        """Durable custody record of one owner-bound step proof."""
        record = self._payload()
        record["proof_sha256"] = self.digest
        return record

    @classmethod
    def from_record(cls, record) -> "CandidateStepProof":
        schema = record.get("schema_version") if isinstance(record, dict) else None
        names = (_LEGACY_FIELDS if schema == LEGACY_STEP_PROOF_SCHEMA
                 else _V2_FIELDS if schema == PREVIOUS_STEP_PROOF_SCHEMA
                 else _V3_FIELDS if schema == STEP_PROOF_SCHEMA
                 else _V4_FIELDS)
        if (not isinstance(record, dict)
                or set(record) != set(names) | {"proof_sha256"}):
            invalid()
        values = {}
        for name in names:
            value = record[name]
            if name == "parameter_names":
                value = tuple(value)
            elif name == "training_authority_members":
                value = tuple(tuple(item) for item in value)
            values[name] = value
        proof = cls(**values)
        if record["proof_sha256"] != proof.digest:
            invalid()
        return proof
