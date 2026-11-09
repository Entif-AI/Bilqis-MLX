"""C02 transport for the exact C03 teacher-visit identity record.

This record is provenance, not an authorization capability.  C02 validates and
binds the upstream identity bytes into its issued batch; it never mints B13/C03
authority from caller primitives.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from collections.abc import Mapping

from bilqis_mlx.errors import ErrorBus, SCHOOL

VISIT_IDENTITY_SCHEMA = "bilqis.bamf.c03-teacher-visit-identity/v1"
SHA256_HEX_LENGTH = hashlib.sha256().digest_size * 2
_VISIT_PROVENANCE_ISSUER = object()


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_TRAINING_ADAPTER.INVALID, reason=reason)


def _hex(value: object) -> bool:
    return (isinstance(value, str) and len(value) == SHA256_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in value))


def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _digest(payload: Mapping) -> str:
    try:
        wire = json.dumps(
            dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        _invalid("VISIT_PROVENANCE_JSON_INVALID")
    return hashlib.sha256(wire.encode()).hexdigest()


@dataclass(frozen=True, init=False)
class BamfVisitProvenance:
    run_identity_sha256: str
    run_seed: int
    generation: int
    accepted_manifest_sha256: str
    teacher_identity: str
    teacher_epoch: int
    student_sha256: str
    selection_seed: int
    cursor: str
    capability_id: str
    policy_key: str
    visit_id: str
    schema: str
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid("VISIT_PROVENANCE_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self) -> None:
        if (getattr(self, "_issuance", None) is not _VISIT_PROVENANCE_ISSUER
                or self.schema != VISIT_IDENTITY_SCHEMA
                or not _hex(self.run_identity_sha256)
                or type(self.run_seed) is not int or self.run_seed < 0
                or type(self.generation) is not int or self.generation < 0
                or not _hex(self.accepted_manifest_sha256)
                or not _hex(self.teacher_identity)
                or type(self.teacher_epoch) is not int or self.teacher_epoch < 0
                or not _hex(self.student_sha256)
                or type(self.selection_seed) is not int or self.selection_seed < 0
                or not all(_name(value) for value in (
                    self.cursor, self.capability_id, self.policy_key))
                or not _hex(self.visit_id)):
            _invalid("VISIT_PROVENANCE_INVALID")

    @classmethod
    def from_c03_record(cls, record: Mapping) -> "BamfVisitProvenance":
        """Parse exact C03 bytes; this authenticates shape/digest, not authority."""
        names = (
            "run_identity_sha256", "run_seed", "generation",
            "accepted_manifest_sha256", "teacher_identity", "teacher_epoch",
            "student_sha256", "selection_seed", "cursor", "capability_id",
            "policy_key", "schema",
        )
        if not isinstance(record, Mapping) or set(record) != set(names) | {"visit_id"}:
            _invalid("VISIT_PROVENANCE_INVALID")
        payload = {name: record[name] for name in names}
        if record["visit_id"] != _digest(payload):
            _invalid("VISIT_PROVENANCE_DIGEST_INVALID")
        value = object.__new__(cls)
        for name in names:
            object.__setattr__(value, name, payload[name])
        object.__setattr__(value, "visit_id", record["visit_id"])
        object.__setattr__(value, "_issuance", _VISIT_PROVENANCE_ISSUER)
        value.__post_init__()
        return value

    def to_c03_record(self) -> dict:
        payload = {
            name: getattr(self, name) for name in (
                "run_identity_sha256", "run_seed", "generation",
                "accepted_manifest_sha256", "teacher_identity", "teacher_epoch",
                "student_sha256", "selection_seed", "cursor", "capability_id",
                "policy_key", "schema")
        }
        return {**payload, "visit_id": self.visit_id}


__all__ = ("BamfVisitProvenance", "VISIT_IDENTITY_SCHEMA")
