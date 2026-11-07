"""Typed records and canonical identities for the C03 teacher lineage."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from collections.abc import Mapping

from bilqis_mlx.errors import ErrorBus, SCHOOL

LINEAGE_SCHEMA = "bilqis.bamf.c03-teacher-lineage/v1"
ADAPTATION_SCHEMA = "bilqis.bamf.teacher-adaptation-authority-ref/v1"
TEACHER_STATE_SCHEMA = "bilqis.mlx.bamf-teacher-state/v1"
HISTORICAL_REPLAY_HEAD = "d21797e72365bf93ea7cad3a4ef9020ec9817f23"
IDENTITY_SCHEMA = "bilqis.bamf.c03-teacher-lineage-identity/v1"


def invalid(reason: str):
    ErrorBus.raise_(SCHOOL.BAMF_TEACHER.INVALID, reason=reason)


def canonical(value: object) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        invalid("TEACHER_LINEAGE_JSON_INVALID")


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def valid_hex(value: object, length: int) -> bool:
    return (isinstance(value, str) and len(value) == length
            and all(char in "0123456789abcdef" for char in value))


def adaptation_authority_ref(
        authority_record: Mapping, *, observed_source_head: str) -> dict:
    """Bind the governing authority record to a separately observed live source head."""
    if (not isinstance(authority_record, Mapping)
            or authority_record.get("schema") != "bilqis.bamf.legacy-trainer-authority/v1"
            or not isinstance(authority_record.get("version"), str)
            or not authority_record["version"]
            or not isinstance(authority_record.get("source_branch"), str)
            or not authority_record["source_branch"]
            or not valid_hex(observed_source_head, 40)):
        invalid("ADAPTATION_AUTHORITY_INVALID")
    return {
        "schema": ADAPTATION_SCHEMA,
        "authority_sha256": digest(authority_record),
        "source_branch": authority_record["source_branch"],
        "observed_source_head": observed_source_head,
    }


def adaptation_ref(record: object) -> dict:
    expected = {"schema", "authority_sha256", "source_branch", "observed_source_head"}
    if (not isinstance(record, Mapping) or set(record) != expected
            or record.get("schema") != ADAPTATION_SCHEMA
            or not valid_hex(record.get("authority_sha256"), 64)
            or not isinstance(record.get("source_branch"), str)
            or not record["source_branch"]
            or not valid_hex(record.get("observed_source_head"), 40)):
        invalid("ADAPTATION_AUTHORITY_INVALID")
    return dict(record)


def student_ref(record: object) -> dict:
    expected = {"schema", "student_sha256", "region"}
    if (not isinstance(record, Mapping) or set(record) != expected
            or record.get("schema") != "bilqis.bamf.student-reference/v1"
            or not valid_hex(record.get("student_sha256"), 64)
            or not isinstance(record.get("region"), str) or not record["region"]):
        invalid("STUDENT_REFERENCE_INVALID")
    return dict(record)


def lineage_identity(source_teacher_sha256: str, adaptation: Mapping,
                     student_sha256: str) -> str:
    return digest({
        "schema": IDENTITY_SCHEMA,
        "historical_replay_head": HISTORICAL_REPLAY_HEAD,
        "adaptation_authority": dict(adaptation),
        "source_teacher_sha256": source_teacher_sha256,
        "student_sha256": student_sha256,
    })


@dataclass(frozen=True)
class TeacherCustodyProjection:
    teacher_state: Mapping
    teacher_identity: str
    teacher_epoch: int

    def __post_init__(self):
        if (not isinstance(self.teacher_state, Mapping)
                or self.teacher_state.get("teacher_identity") != self.teacher_identity
                or self.teacher_state.get("teacher_epoch") != self.teacher_epoch
                or not valid_hex(self.teacher_identity, 64)
                or type(self.teacher_epoch) is not int or self.teacher_epoch < 0):
            invalid("TEACHER_CUSTODY_PROJECTION_INVALID")
