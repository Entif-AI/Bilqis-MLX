"""Structural extraction from akasha_outbox.py; behavior preserved."""
from __future__ import annotations
from enum import Enum
import hashlib
import json
import re
from types import MappingProxyType
from ..errors import ErrorBus, SCHOOL

AKASHA_EVENT_SCHEMA = "bilqis.c10.akasha-event/v1"

AKASHA_PROJECTION_SCHEMA = "bilqis.c10.akasha-projection/v1"

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")

_DELIVERY_STATUSES = frozenset({"FAILED", "DELIVERED"})

def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_AKASHA.INVALID, reason=reason)

def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def _canonical(value: object) -> str:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        _invalid("BAMF_C10_PAYLOAD_NOT_CANONICAL")

def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))

def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value)

def _time(value: object) -> bool:
    return type(value) is int and value >= 0

class AkashaEventKind(str, Enum):
    BANK_ALLOCATION = "BANK_ALLOCATION"
    PLASTICITY_EPOCH = "PLASTICITY_EPOCH"
    PACKAGE_EXPORT = "PACKAGE_EXPORT"
    TEACHER_VISIT = "TEACHER_VISIT"
    FACTORY_RELEASE = "FACTORY_RELEASE"
    CAPABILITY_OUTCOME = "CAPABILITY_OUTCOME"
    SOURCE_CORRECTION = "SOURCE_CORRECTION"
    REVALIDATION = "REVALIDATION"
    REQUALIFICATION = "REQUALIFICATION"
    CAPABILITY_GRADUATION = "CAPABILITY_GRADUATION"
    MOTIF_CANDIDATE = "MOTIF_CANDIDATE"
    PROCESS_FAULT = "PROCESS_FAULT"
    CHECKPOINT_PUBLICATION = "CHECKPOINT_PUBLICATION"

NATIVE_EVENT_KINDS = MappingProxyType({
    'SCHOOL_TEACHER_VISIT_COMMITTED': AkashaEventKind.TEACHER_VISIT,
    'SCHOOL_FACTORY_RELEASE_MIGRATED': AkashaEventKind.FACTORY_RELEASE,
    'SCHOOL_EXECUTION_PROFILE_ADOPTED': AkashaEventKind.FACTORY_RELEASE,
    'SCHOOL_SEMANTIC_CATALOG_PROFILE_ADOPTED': AkashaEventKind.FACTORY_RELEASE,
    'SCHOOL_CAPABILITY_BEST_COMMITTED': AkashaEventKind.CAPABILITY_OUTCOME,
})

OWNER_FIXTURE_KINDS = (AkashaEventKind.BANK_ALLOCATION, AkashaEventKind.PLASTICITY_EPOCH, AkashaEventKind.PACKAGE_EXPORT)

_REQUIRED_FIELDS = MappingProxyType({
    **{kind: frozenset({"owner_source_event_id", "producer_id", "artifact_schema", "artifact_sha256", "verification_mode"})
       for kind in OWNER_FIXTURE_KINDS},
    **{kind: frozenset({"native_event_id", "native_event_digest", "run_id", "generation", "native_event_type"})
       for kind in (AkashaEventKind.TEACHER_VISIT, AkashaEventKind.FACTORY_RELEASE, AkashaEventKind.CAPABILITY_OUTCOME)},
    AkashaEventKind.SOURCE_CORRECTION: frozenset({
        "correction_event_id", "source_owner", "dependency_key",
        "old_digest", "new_digest"}),
    AkashaEventKind.REVALIDATION: frozenset({
        "artifact_id", "old_digest", "new_digest", "eligible"}),
    AkashaEventKind.REQUALIFICATION: frozenset({
        "capability_id", "retained_generation_sha256", "status"}),
    AkashaEventKind.CAPABILITY_GRADUATION: frozenset({
        "capability_id", "generation_sha256", "assessment_receipt_sha256"}),
    AkashaEventKind.MOTIF_CANDIDATE: frozenset({
        "motif_id", "source_refs", "eligibility_digest"}),
    AkashaEventKind.PROCESS_FAULT: frozenset({
        "fault_id", "original_source_event_id", "correction_event_id",
        "remediation_id", "derived_path"}),
    AkashaEventKind.CHECKPOINT_PUBLICATION: frozenset({
        "checkpoint_digest", "generation_sha256", "manifest_digest"}),
})

_DIGEST_FIELDS = frozenset({
    "native_event_digest", "artifact_sha256",
    "old_digest", "new_digest", "retained_generation_sha256",
    "generation_sha256", "assessment_receipt_sha256",
    "eligibility_digest", "checkpoint_digest", "manifest_digest",
})

_NONEMPTY_LIST_FIELDS = frozenset({"source_refs", "derived_path"})

def _payload_for(kind: AkashaEventKind, payload_json: str) -> dict:
    try:
        payload = json.loads(payload_json)
    except (TypeError, ValueError):
        _invalid("BAMF_C10_PAYLOAD_NOT_CANONICAL")
    if (not isinstance(payload, dict)
            or any(not isinstance(key, str) for key in payload)
            or not _REQUIRED_FIELDS[kind].issubset(payload)
            or payload_json != _canonical(payload)):
        _invalid("BAMF_C10_PROJECTION_FIELDS_INVALID")
    for key in _REQUIRED_FIELDS[kind]:
        value = payload[key]
        if value is None or value == "" or value == []:
            _invalid("BAMF_C10_PROJECTION_FIELDS_INVALID")
        if key in _DIGEST_FIELDS and not _sha(value):
            _invalid("BAMF_C10_PROJECTION_FIELDS_INVALID")
        if (key in _NONEMPTY_LIST_FIELDS
                and (not isinstance(value, list)
                     or not value
                     or any(not _name(item) for item in value))):
            _invalid("BAMF_C10_PROJECTION_FIELDS_INVALID")
    if kind in OWNER_FIXTURE_KINDS:
        if (payload['verification_mode'] != 'DISPOSABLE_CONTRACT'
                or any(not _name(payload[key]) for key in ('owner_source_event_id', 'producer_id', 'artifact_schema'))):
            _invalid("BAMF_C10_PROJECTION_FIELDS_INVALID")
    if kind in NATIVE_EVENT_KINDS.values():
        if (type(payload['generation']) is not int or payload['generation'] < 0
                or not _name(payload['run_id']) or not _sha(payload['native_event_id'])
                or not _name(payload['native_event_type'])
                or NATIVE_EVENT_KINDS.get(payload['native_event_type']) is not kind):
            _invalid("BAMF_C10_PROJECTION_FIELDS_INVALID")
    if (kind is AkashaEventKind.REVALIDATION
            and type(payload["eligible"]) is not bool):
        _invalid("BAMF_C10_PROJECTION_FIELDS_INVALID")
    if (kind is AkashaEventKind.REQUALIFICATION
            and payload["status"] not in (
                "QUALIFIED", "REQUALIFICATION_REQUIRED")):
        _invalid("BAMF_C10_PROJECTION_FIELDS_INVALID")
    return payload
