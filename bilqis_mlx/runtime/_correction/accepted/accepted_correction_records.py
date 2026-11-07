"""Canonical codecs for accepted-generation C09 evidence records."""
from __future__ import annotations

import hashlib
import json

from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef
from bilqis_mlx.semantics.context_eligibility import C09ContextInvalidation
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
ACCEPTED_EVENT_TYPES = frozenset((
    CORRECTION_EVENT, REVALIDATION_EVENT, CONTEXT_INVALIDATION_EVENT, REMEDIATION_EVENT,
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


def _context_invalidation_payload(event: C09ContextInvalidation) -> dict:
    if not isinstance(event, C09ContextInvalidation):
        _invalid("BAMF_C09_CONTEXT_INVALIDATION_REQUIRED")
    return {
        "context_event_id": event.event_id,
        "old_context_digest": event.old_context_digest,
        "new_context_digest": event.new_context_digest,
        "reason_codes": list(event.reason_codes),
        "principal_id": event.principal_id,
        "tenant_id": event.tenant_id,
        "scope": event.scope,
        "semantic_release": event.semantic_release,
        "policy_epoch": event.policy_epoch,
        "rights_epoch": event.rights_epoch,
        "correction_generation": event.correction_generation,
        "causal_prefix_end": event.causal_prefix_end,
        "invalidated_handles": list(event.invalidated_handles),
        "schema_version": event.schema_version,
    }


def context_invalidation_record(
    manifest_sha256: str, event: C09ContextInvalidation,
) -> dict:
    body = {
        "event": CONTEXT_INVALIDATION_EVENT,
        "accepted_manifest_sha256": manifest_sha256,
        "context_invalidation": _context_invalidation_payload(event),
    }
    return {"event_id": hashlib.sha256(_canonical(body)).hexdigest(), **body}


def context_invalidation_from_record(record: dict) -> C09ContextInvalidation:
    expected = {
        "context_event_id", "old_context_digest", "new_context_digest", "reason_codes",
        "principal_id", "tenant_id", "scope", "semantic_release",
        "policy_epoch", "rights_epoch", "correction_generation",
        "causal_prefix_end", "invalidated_handles", "schema_version",
    }
    try:
        payload = record["context_invalidation"]
        if not isinstance(payload, dict) or set(payload) != expected:
            _invalid("BAMF_C09_CONTEXT_INVALIDATION_LEDGER_INVALID")
        if (type(payload["reason_codes"]) is not list
                or type(payload["invalidated_handles"]) is not list):
            _invalid("BAMF_C09_CONTEXT_INVALIDATION_LEDGER_INVALID")
        event = C09ContextInvalidation(
            old_context_digest=payload["old_context_digest"],
            new_context_digest=payload["new_context_digest"],
            reason_codes=tuple(payload["reason_codes"]),
            principal_id=payload["principal_id"],
            tenant_id=payload["tenant_id"],
            scope=payload["scope"],
            semantic_release=payload["semantic_release"],
            policy_epoch=payload["policy_epoch"],
            rights_epoch=payload["rights_epoch"],
            correction_generation=payload["correction_generation"],
            causal_prefix_end=payload["causal_prefix_end"],
            invalidated_handles=tuple(payload["invalidated_handles"]),
            schema_version=payload["schema_version"],
        )
        if event.event_id != payload["context_event_id"]:
            _invalid("BAMF_C09_CONTEXT_INVALIDATION_LEDGER_DRIFT")
        return event
    except (KeyError, TypeError, ValueError):
        _invalid("BAMF_C09_CONTEXT_INVALIDATION_LEDGER_INVALID")


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
    "ACCEPTED_EVENT_TYPES", "CONTEXT_INVALIDATION_EVENT", "CORRECTION_EVENT", "DERIVED_CLAIM_EVENT",
    "PROCESS_FAULT_EVENT", "REMEDIATION_EVENT", "REVALIDATION_EVENT",
    "_canonical", "context_invalidation_from_record", "context_invalidation_record",
    "correction_record", "frontier_from_record",
    "lineage_records_from_bytes", "records_from_bytes", "revalidation_record",
    "validate_record",
)
