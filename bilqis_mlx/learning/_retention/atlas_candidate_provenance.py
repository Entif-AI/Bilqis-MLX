"""B12 candidate custody identities and durable step proofs."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

from bilqis_mlx.errors import ErrorBus, SCHOOL


STEP_PROOF_SCHEMA = "bilqis.mlx.candidate-step-proof/v1"
DIGEST_HEX_LENGTH = 64


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _is_digest(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == DIGEST_HEX_LENGTH
        and all(char in "0123456789abcdef" for char in value)
    )


def candidate_identity_digest(state) -> str:
    """Digest the exact optimizer state used as the B12 parent identity."""
    import numpy as np

    optimizer = state.optimizer
    parts = {
        group: {
            name: np.asarray(value).tobytes().hex()
            for name, value in sorted(getattr(optimizer, group).items())
        }
        for group in ("parameters", "m", "v", "update_counts")
    }
    payload = json.dumps(
        {"state": parts, "optimizer_step": state.optimizer_step},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256((payload + "\n").encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CandidateCustodyIdentity:
    """Published identity of one accepted generation."""

    run_id: str
    generation: int
    manifest_sha256: str | None
    topology_digest: str
    extents_digest: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.run_id, str)
            or not self.run_id
            or type(self.generation) is not int
            or self.generation < 0
            or (
                self.manifest_sha256 is not None
                and not _is_digest(self.manifest_sha256)
            )
            or not _is_digest(self.topology_digest)
            or not _is_digest(self.extents_digest)
        ):
            _invalid()


@dataclass(frozen=True)
class CandidateStepProof:
    """Durable proof that one optimizer step used owner-issued provenance."""

    step_index: int
    provenance_sha256: str
    participation_sha256: str
    mask_sha256: str
    parameter_names: tuple[str, ...]
    loss_bearing: bool
    schema_version: str = STEP_PROOF_SCHEMA

    def __post_init__(self) -> None:
        if (
            type(self.step_index) is not int
            or self.step_index < 1
            or not _is_digest(self.provenance_sha256)
            or not _is_digest(self.participation_sha256)
            or not _is_digest(self.mask_sha256)
            or type(self.parameter_names) is not tuple
            or self.parameter_names != tuple(sorted(set(self.parameter_names)))
            or any(not isinstance(name, str) or not name for name in self.parameter_names)
            or type(self.loss_bearing) is not bool
            or self.schema_version != STEP_PROOF_SCHEMA
        ):
            _invalid()

    @property
    def digest(self) -> str:
        payload = json.dumps(
            asdict(self),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_record(self) -> dict:
        record = asdict(self)
        record["proof_sha256"] = self.digest
        return record

    @classmethod
    def from_record(cls, record) -> "CandidateStepProof":
        names = (
            "step_index",
            "provenance_sha256",
            "participation_sha256",
            "mask_sha256",
            "parameter_names",
            "loss_bearing",
            "schema_version",
        )
        if not isinstance(record, dict) or set(record) != set(names) | {"proof_sha256"}:
            _invalid()
        proof = cls(
            **{
                name: tuple(record[name]) if name == "parameter_names" else record[name]
                for name in names
            }
        )
        if record["proof_sha256"] != proof.digest:
            _invalid()
        return proof
