"""Historical acceptance-record schemas and fail-closed parsing."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from bilqis_mlx.errors import ErrorBus, SCHOOL

LEGACY_ACCEPTANCE_SCHEMA = "bilqis.mlx.accepted-candidate-binding/v1"
PREVIOUS_ACCEPTANCE_SCHEMA = "bilqis.mlx.accepted-candidate-binding/v2"
PREVIOUS_SOURCE_ACCEPTANCE_SCHEMA = "bilqis.mlx.accepted-candidate-binding/v3"
PREVIOUS_DEPENDENCY_ACCEPTANCE_SCHEMA = "bilqis.mlx.accepted-candidate-binding/v4"
ACCEPTANCE_SCHEMA = "bilqis.mlx.accepted-candidate-binding/v5"
MOTIF_ACCEPTANCE_SCHEMA = "bilqis.mlx.accepted-candidate-binding/v6"
DIGEST_HEX_LENGTH = 64
LEGACY_FIELDS = (
    "run_id", "generation", "candidate_identity_sha256", "feature_sha256",
    "optimizer_step", "retention_reason", "step_proof_sha256",
    "decision_sha256", "schema_version",
)
V2_BINDING_FIELDS = (
    "run_id", "generation", "candidate_identity_sha256",
    "parent_candidate_identity_sha256", "feature_sha256", "optimizer_step",
    "retention_reason", "step_proof_sha256", "decision_sha256",
    "evidence_sha256", "policy_sha256", "schema_version",
)
V3_BINDING_FIELDS = V2_BINDING_FIELDS[:-1] + ("source_anchors", "schema_version")
V4_BINDING_FIELDS = V3_BINDING_FIELDS
BINDING_FIELDS = V4_BINDING_FIELDS[:-1] + (
    "source_authority_registry_sha256", "schema_version")
MOTIF_BINDING_FIELDS = BINDING_FIELDS[:-1] + (
    "generation_authority_sha256", "schema_version")
V3_SOURCE_ANCHOR_WIDTH = 9
SOURCE_ANCHOR_WIDTH = 10
DEPENDENCY_RECORD_WIDTH = 2
SOURCE_ANCHOR_DIGEST_INDEXES = (2, 5, 6, 7, 8)
SOURCE_ANCHOR_DEPENDENCIES_INDEX = 9


def invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def is_digest(value) -> bool:
    return (isinstance(value, str) and len(value) == DIGEST_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in value))


def canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def dependency_records(value) -> bool:
    return (type(value) is tuple and value
            and all(type(item) is tuple and len(item) == DEPENDENCY_RECORD_WIDTH
                    and all(isinstance(part, str) and part for part in item)
                    for item in value)
            and value == tuple(sorted(set(value))))


def normalize_source_anchors(value, schema):
    if not isinstance(value, (tuple, list)):
        invalid()
    normalized = []
    for anchor in value:
        if not isinstance(anchor, (tuple, list)):
            invalid()
        anchor = tuple(anchor)
        if schema in (
                PREVIOUS_DEPENDENCY_ACCEPTANCE_SCHEMA, ACCEPTANCE_SCHEMA,
                MOTIF_ACCEPTANCE_SCHEMA):
            if len(anchor) != SOURCE_ANCHOR_WIDTH:
                invalid()
            dependencies = anchor[-1]
            if not isinstance(dependencies, (tuple, list)):
                invalid()
            anchor = (*anchor[:-1], tuple(
                tuple(item) if isinstance(item, (tuple, list)) else item
                for item in dependencies))
        normalized.append(anchor)
    return tuple(normalized)


def valid_source_anchors(value, schema=ACCEPTANCE_SCHEMA) -> bool:
    if type(value) is not tuple:
        return False
    width = (SOURCE_ANCHOR_WIDTH if schema in (
                 PREVIOUS_DEPENDENCY_ACCEPTANCE_SCHEMA, ACCEPTANCE_SCHEMA,
                 MOTIF_ACCEPTANCE_SCHEMA)
             else V3_SOURCE_ANCHOR_WIDTH)
    for anchor in value:
        if type(anchor) is not tuple or len(anchor) != width:
            return False
        strings = anchor[:SOURCE_ANCHOR_DEPENDENCIES_INDEX]
        if (not all(isinstance(item, str) and item for item in strings)
                or not all(is_digest(strings[index])
                           for index in SOURCE_ANCHOR_DIGEST_INDEXES)):
            return False
        if (schema in (
                PREVIOUS_DEPENDENCY_ACCEPTANCE_SCHEMA, ACCEPTANCE_SCHEMA,
                MOTIF_ACCEPTANCE_SCHEMA)
                and not dependency_records(
                    anchor[SOURCE_ANCHOR_DEPENDENCIES_INDEX])):
            return False
    return True


@dataclass(frozen=True)
class ParsedAcceptedCandidateBinding:
    """Verified custody evidence, never accepted as a live publication token."""
    fields: dict

    def __getattr__(self, name: str):
        known = (LEGACY_FIELDS, V2_BINDING_FIELDS, V3_BINDING_FIELDS,
                 V4_BINDING_FIELDS, BINDING_FIELDS, MOTIF_BINDING_FIELDS)
        if any(name in fields for fields in known):
            return self.fields.get(name)
        raise AttributeError(name)

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical(self.fields)).hexdigest()

    def to_record(self) -> dict:
        return {**self.fields, "binding_sha256": self.digest}


def parse_accepted_candidate_binding(record) -> ParsedAcceptedCandidateBinding:
    if not isinstance(record, dict):
        invalid()
    schema = record.get("schema_version")
    names = (LEGACY_FIELDS if schema == LEGACY_ACCEPTANCE_SCHEMA
             else V2_BINDING_FIELDS if schema == PREVIOUS_ACCEPTANCE_SCHEMA
             else V3_BINDING_FIELDS if schema == PREVIOUS_SOURCE_ACCEPTANCE_SCHEMA
             else V4_BINDING_FIELDS if schema == PREVIOUS_DEPENDENCY_ACCEPTANCE_SCHEMA
             else BINDING_FIELDS if schema == ACCEPTANCE_SCHEMA
             else MOTIF_BINDING_FIELDS if schema == MOTIF_ACCEPTANCE_SCHEMA else ())
    if not names or set(record) != set(names) | {"binding_sha256"}:
        invalid()
    if (not isinstance(record["run_id"], str) or not record["run_id"]
            or type(record["generation"]) is not int or record["generation"] < 0
            or type(record["optimizer_step"]) is not int or record["optimizer_step"] < 0
            or not isinstance(record["retention_reason"], str)
            or not record["retention_reason"]
            or not isinstance(record["step_proof_sha256"], (tuple, list))
            or any(not is_digest(value) for value in record["step_proof_sha256"])
            or any(not is_digest(record[name]) for name in (
                "candidate_identity_sha256", "feature_sha256", "decision_sha256"))):
        invalid()
    if names in (V2_BINDING_FIELDS, V4_BINDING_FIELDS, BINDING_FIELDS,
                 MOTIF_BINDING_FIELDS) and any(
            not is_digest(record[name]) for name in (
                "parent_candidate_identity_sha256", "evidence_sha256", "policy_sha256")):
        invalid()
    anchors = None
    if names in (V3_BINDING_FIELDS, V4_BINDING_FIELDS, BINDING_FIELDS,
                 MOTIF_BINDING_FIELDS):
        anchors = normalize_source_anchors(record.get("source_anchors"), schema)
        if not valid_source_anchors(anchors, schema):
            invalid()
    if (names in (BINDING_FIELDS, MOTIF_BINDING_FIELDS)
            and record["source_authority_registry_sha256"] is not None
            and not is_digest(record["source_authority_registry_sha256"])):
        invalid()
    if names == MOTIF_BINDING_FIELDS and not is_digest(record["generation_authority_sha256"]):
        invalid()
    payload = {name: record[name] for name in names}
    if anchors is not None:
        payload["source_anchors"] = anchors
    if record["binding_sha256"] != hashlib.sha256(canonical(payload)).hexdigest():
        invalid()
    payload["step_proof_sha256"] = tuple(payload["step_proof_sha256"])
    return ParsedAcceptedCandidateBinding(payload)
