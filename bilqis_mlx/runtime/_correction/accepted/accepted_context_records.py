"""Typed accepted C09 context invalidation and revalidation codecs."""
from __future__ import annotations

import hashlib

from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef
from bilqis_mlx.semantics.context_eligibility import (
    C09ContextInvalidation,
    C09_INVALIDATION_SCHEMA_V1,
    C09_INVALIDATION_SCHEMA_V2,
)

from .accepted_correction_records import (
    CONTEXT_INVALIDATION_EVENT,
    CONTEXT_REVALIDATION_EVENT,
    _canonical,
)
from .atlas_revalidation_common import _invalid
from .context_revalidation import (
    ContextRevalidatedArtifact,
    ContextRevalidationFrontier,
)


def _context_invalidation_payload(event: C09ContextInvalidation) -> dict:
    if not isinstance(event, C09ContextInvalidation):
        _invalid("BAMF_C09_CONTEXT_INVALIDATION_REQUIRED")
    payload = {
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
    if event.schema_version == C09_INVALIDATION_SCHEMA_V2:
        payload.update({
            "source_time": event.source_time,
            "effective_time": event.effective_time,
            "observed_at": event.observed_at,
            "recorded_at": event.recorded_at,
            "temporal_authority_sha256": event.temporal_authority_sha256,
        })
    return payload


def context_invalidation_record(
    manifest_sha256: str, event: C09ContextInvalidation,
    temporal_authority=None,
) -> dict:
    if (event.schema_version == C09_INVALIDATION_SCHEMA_V2
            and temporal_authority is None):
        _invalid("BAMF_C09_CONTEXT_TEMPORAL_AUTHORITY_REQUIRED")
    if temporal_authority is not None:
        from bilqis_mlx.factory.skos_curriculum.source_context_policy import (
            source_context_temporal_identity,
        )
        temporal = source_context_temporal_identity(temporal_authority)
        if (event.schema_version != C09_INVALIDATION_SCHEMA_V2
                or (event.source_time, event.effective_time,
                    event.observed_at, event.recorded_at,
                    event.temporal_authority_sha256)
                != (temporal["source_time"], temporal["effective_time"],
                    temporal["observed_at"], temporal["recorded_at"],
                    temporal["authority_registry_sha256"])):
            _invalid("BAMF_C09_CONTEXT_TEMPORAL_IDENTITY_DRIFT")
    body = {
        "event": CONTEXT_INVALIDATION_EVENT,
        "accepted_manifest_sha256": manifest_sha256,
        "context_invalidation": _context_invalidation_payload(event),
    }
    return {"event_id": hashlib.sha256(_canonical(body)).hexdigest(), **body}


def _validate_source_temporal_identity(event: C09ContextInvalidation) -> dict:
    from bilqis_mlx.factory.skos_curriculum.source_context_policy import (
        SOURCE_CONTEXT_TEMPORAL_IDENTITY_SCHEMA,
        validate_source_context_temporal_identity,
    )
    return validate_source_context_temporal_identity({
        "source_time": event.source_time,
        "effective_time": event.effective_time,
        "observed_at": event.observed_at,
        "recorded_at": event.recorded_at,
        "authority_registry_sha256": event.temporal_authority_sha256,
        "schema_version": SOURCE_CONTEXT_TEMPORAL_IDENTITY_SCHEMA,
    })


def context_invalidation_from_record(record: dict) -> C09ContextInvalidation:
    legacy_expected = {
        "context_event_id", "old_context_digest", "new_context_digest", "reason_codes",
        "principal_id", "tenant_id", "scope", "semantic_release",
        "policy_epoch", "rights_epoch", "correction_generation",
        "causal_prefix_end", "invalidated_handles", "schema_version",
    }
    current_expected = legacy_expected | {
        "source_time", "effective_time", "observed_at", "recorded_at",
        "temporal_authority_sha256",
    }
    try:
        payload = record["context_invalidation"]
        if not isinstance(payload, dict):
            _invalid("BAMF_C09_CONTEXT_INVALIDATION_LEDGER_INVALID")
        schema = payload.get("schema_version")
        expected = (
            legacy_expected if schema == C09_INVALIDATION_SCHEMA_V1
            else current_expected if schema == C09_INVALIDATION_SCHEMA_V2
            else None
        )
        if expected is None or set(payload) != expected:
            _invalid("BAMF_C09_CONTEXT_INVALIDATION_LEDGER_INVALID")
        if (type(payload["reason_codes"]) is not list
                or type(payload["invalidated_handles"]) is not list):
            _invalid("BAMF_C09_CONTEXT_INVALIDATION_LEDGER_INVALID")
        event = C09ContextInvalidation(
            old_context_digest=payload["old_context_digest"],
            new_context_digest=payload["new_context_digest"],
            reason_codes=tuple(payload["reason_codes"]),
            principal_id=payload["principal_id"],
            tenant_id=payload["tenant_id"], scope=payload["scope"],
            semantic_release=payload["semantic_release"],
            policy_epoch=payload["policy_epoch"], rights_epoch=payload["rights_epoch"],
            correction_generation=payload["correction_generation"],
            causal_prefix_end=payload["causal_prefix_end"],
            invalidated_handles=tuple(payload["invalidated_handles"]),
            source_time=payload.get("source_time"),
            effective_time=payload.get("effective_time"),
            observed_at=payload.get("observed_at"),
            recorded_at=payload.get("recorded_at"),
            temporal_authority_sha256=payload.get("temporal_authority_sha256"),
            schema_version=payload["schema_version"],
        )
        if event.event_id != payload["context_event_id"]:
            _invalid("BAMF_C09_CONTEXT_INVALIDATION_LEDGER_DRIFT")
        if event.schema_version == C09_INVALIDATION_SCHEMA_V2:
            _validate_source_temporal_identity(event)
        return event
    except (KeyError, TypeError, ValueError):
        _invalid("BAMF_C09_CONTEXT_INVALIDATION_LEDGER_INVALID")


def context_temporal_identity_from_record(record: dict) -> dict:
    event = context_invalidation_from_record(record)
    if event.schema_version != C09_INVALIDATION_SCHEMA_V2:
        _invalid("BAMF_C09_CONTEXT_TEMPORAL_IDENTITY_REQUIRED")
    return _validate_source_temporal_identity(event)


def context_revalidation_record(
    manifest_sha256: str, frontier: ContextRevalidationFrontier,
) -> dict:
    if not isinstance(frontier, ContextRevalidationFrontier):
        _invalid("BAMF_C09_CONTEXT_REVALIDATION_FRONTIER_REQUIRED")
    body = {
        "event": CONTEXT_REVALIDATION_EVENT,
        "accepted_manifest_sha256": manifest_sha256,
        "frontier": [{
            "artifact_id": item.artifact_id,
            "immediate_dependencies": [
                {"kind": ref.kind.value, "key": ref.key}
                for ref in item.immediate_dependencies
            ],
            "content_digest": item.content_digest, "eligible": item.eligible,
            "source_receipt_sha256": item.source_receipt_sha256,
            "context_event_id": item.context_event_id,
            "context_invalidation_receipt_sha256":
                item.context_invalidation_receipt_sha256,
            "source_owner": item.source_owner,
            "source_signature_hex": item.source_signature_hex,
            "schema_version": item.schema_version,
        } for item in frontier.results],
    }
    return {"event_id": hashlib.sha256(_canonical(body)).hexdigest(), **body}


def context_frontier_from_record(record: dict) -> ContextRevalidationFrontier:
    try:
        results = tuple(sorted((ContextRevalidatedArtifact(
            artifact_id=item["artifact_id"],
            immediate_dependencies=tuple(sorted(
                DependencyRef(DependencyKind(ref["kind"]), ref["key"])
                for ref in item["immediate_dependencies"])),
            content_digest=item["content_digest"], eligible=item["eligible"],
            source_receipt_sha256=item["source_receipt_sha256"],
            context_event_id=item["context_event_id"],
            context_invalidation_receipt_sha256=
                item["context_invalidation_receipt_sha256"],
            source_owner=item["source_owner"],
            source_signature_hex=item["source_signature_hex"],
            schema_version=item["schema_version"],
        ) for item in record["frontier"]), key=lambda item: item.artifact_id))
        return ContextRevalidationFrontier(results)
    except (KeyError, TypeError, ValueError):
        _invalid("BAMF_C09_CONTEXT_REVALIDATION_LEDGER_INVALID")


__all__ = (
    "context_frontier_from_record",
    "context_invalidation_from_record",
    "context_invalidation_record",
    "context_revalidation_record",
    "context_temporal_identity_from_record",
)
