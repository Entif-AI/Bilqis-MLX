"""Canonical codecs for accepted-generation C09 evidence records."""
from __future__ import annotations

import hashlib
import json

from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef
from bilqis_mlx.runtime.capability_support_journal import _event_record

from .accepted_stale_replay_ledger import (
    DERIVED_CLAIM_EVENT, PROCESS_FAULT_EVENT, REMEDIATION_EVENT,
)
from .atlas_revalidation_common import _invalid
from .atlas_revalidation_evidence import (
    CorrectionEvent, RevalidatedArtifact, RevalidationFrontier,
)


CORRECTION_EVENT = "BAMF_C09_CORRECTION"
REVALIDATION_EVENT = "BAMF_C09_REVALIDATION"
CONTEXT_INVALIDATION_EVENT = "BAMF_C09_CONTEXT_INVALIDATION"
CONTEXT_REVALIDATION_EVENT = "BAMF_C09_CONTEXT_REVALIDATION"
ACCEPTED_EVENT_TYPES = frozenset((
    CORRECTION_EVENT, REVALIDATION_EVENT, CONTEXT_INVALIDATION_EVENT,
    CONTEXT_REVALIDATION_EVENT, REMEDIATION_EVENT,
    DERIVED_CLAIM_EVENT, PROCESS_FAULT_EVENT,
))


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def correction_record(manifest_sha256: str, event: CorrectionEvent) -> dict:
    body = {
        "event": CORRECTION_EVENT,
        "accepted_manifest_sha256": manifest_sha256,
        "correction": _event_record(event),
    }
    return {"event_id": hashlib.sha256(_canonical(body)).hexdigest(), **body}


def _revalidation_payload(frontier: RevalidationFrontier) -> list[dict]:
    return [
        {
            "artifact_id": item.artifact_id,
            "immediate_dependencies": [
                {"kind": ref.kind.value, "key": ref.key}
                for ref in item.immediate_dependencies
            ],
            "content_digest": item.content_digest,
            "eligible": item.eligible,
            "source_receipt_sha256": item.source_receipt_sha256,
            "correction_event_id": item.correction_event_id,
            "correction_receipt_sha256": item.correction_receipt_sha256,
            "source_owner": item.source_owner,
            "source_signature_hex": item.source_signature_hex,
        }
        for item in frontier.results
    ]


def revalidation_record(
    manifest_sha256: str, frontier: RevalidationFrontier,
) -> dict:
    if not isinstance(frontier, RevalidationFrontier):
        _invalid("BAMF_C09_REVALIDATION_FRONTIER_REQUIRED")
    body = {
        "event": REVALIDATION_EVENT,
        "accepted_manifest_sha256": manifest_sha256,
        "frontier": _revalidation_payload(frontier),
    }
    return {"event_id": hashlib.sha256(_canonical(body)).hexdigest(), **body}


def frontier_from_record(record: dict) -> RevalidationFrontier:
    try:
        results = tuple(sorted((
            RevalidatedArtifact(
                artifact_id=item["artifact_id"],
                immediate_dependencies=tuple(sorted(
                    DependencyRef(DependencyKind(ref["kind"]), ref["key"])
                    for ref in item["immediate_dependencies"]
                )),
                content_digest=item["content_digest"],
                eligible=item["eligible"],
                source_receipt_sha256=item["source_receipt_sha256"],
                correction_event_id=item["correction_event_id"],
                correction_receipt_sha256=item["correction_receipt_sha256"],
                source_owner=item["source_owner"],
                source_signature_hex=item["source_signature_hex"],
            )
            for item in record["frontier"]
        ), key=lambda item: item.artifact_id))
        return RevalidationFrontier(results)
    except (KeyError, TypeError, ValueError):
        _invalid("BAMF_C09_REVALIDATION_LEDGER_INVALID")


def validate_record(record: dict, manifest_sha256: str) -> dict:
    if (not isinstance(record, dict)
            or record.get("accepted_manifest_sha256") != manifest_sha256
            or record.get("event") not in ACCEPTED_EVENT_TYPES):
        _invalid("BAMF_C09_CORRECTION_LEDGER_INVALID")
    body = {key: value for key, value in record.items() if key != "event_id"}
    if record.get("event_id") != hashlib.sha256(_canonical(body)).hexdigest():
        _invalid("BAMF_C09_CORRECTION_LEDGER_DRIFT")
    return record


def records_from_bytes(raw: bytes, manifest_sha256: str) -> tuple[dict, ...]:
    if not raw:
        return ()
    records = []
    try:
        for encoded in raw.splitlines(keepends=True):
            if not encoded.endswith(b"\n"):
                _invalid("BAMF_C09_CORRECTION_LEDGER_TRUNCATED")
            item = json.loads(encoded.decode("utf-8"))
            if (not isinstance(item, dict)
                    or item.get("accepted_manifest_sha256") != manifest_sha256
                    or item.get("event") not in ACCEPTED_EVENT_TYPES):
                continue
            records.append(validate_record(item, manifest_sha256))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _invalid("BAMF_C09_CORRECTION_LEDGER_INVALID")
    by_id = {}
    ordered = []
    for item in records:
        event_id = item["event_id"]
        prior = by_id.get(event_id)
        if prior is not None and prior != item:
            _invalid("BAMF_C09_CORRECTION_LEDGER_CONFLICT")
        if prior is None:
            by_id[event_id] = item
            ordered.append(item)
    return tuple(ordered)


def lineage_records_from_bytes(
    raw: bytes, manifest_sha256s: tuple[str, ...],
) -> tuple[dict, ...]:
    """Decode one physical ledger in append order for an accepted manifest lineage."""
    if not raw:
        return ()
    allowed = frozenset(manifest_sha256s)
    records = []
    try:
        for encoded in raw.splitlines(keepends=True):
            if not encoded.endswith(b"\n"):
                _invalid("BAMF_C09_CORRECTION_LEDGER_TRUNCATED")
            item = json.loads(encoded.decode("utf-8"))
            if (not isinstance(item, dict)
                    or item.get("accepted_manifest_sha256") not in allowed
                    or item.get("event") not in ACCEPTED_EVENT_TYPES):
                continue
            records.append(validate_record(
                item, item["accepted_manifest_sha256"]))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _invalid("BAMF_C09_CORRECTION_LEDGER_INVALID")
    by_id = {}
    ordered = []
    for item in records:
        event_id = item["event_id"]
        prior = by_id.get(event_id)
        if prior is not None and prior != item:
            _invalid("BAMF_C09_CORRECTION_LEDGER_CONFLICT")
        if prior is None:
            by_id[event_id] = item
            ordered.append(item)
    return tuple(ordered)


__all__ = (
    "ACCEPTED_EVENT_TYPES", "CONTEXT_INVALIDATION_EVENT",
    "CONTEXT_REVALIDATION_EVENT", "CORRECTION_EVENT", "DERIVED_CLAIM_EVENT",
    "PROCESS_FAULT_EVENT", "REMEDIATION_EVENT", "REVALIDATION_EVENT",
    "_canonical", "correction_record", "frontier_from_record",
    "lineage_records_from_bytes", "records_from_bytes", "revalidation_record",
    "validate_record",
)
