"""Immutable request and packet contracts for BAMF source prefetch."""
from __future__ import annotations

import hashlib
import json

from bilqis_mlx.factory.teaching import optional_teaching_rows
from bilqis_mlx.runtime.source_execution import source_content_digest
from bilqis_mlx.runtime.source_prefetch import (
    FORBIDDEN_AUTHORITY_KEYS, ImmutableSourcePacket, SCHEMA, freeze_source_packet,
)
from bilqis_mlx.semantics.domains import contract_digest

from .session_parts.fresh_support import FreshSupportSpecimen
from .session_parts.rehearsal import materialize_rehearsal_rows


REQUEST_SCHEMA = "bilqis.bamf.native-source-prefetch-request/v1"
_BASE_REQUEST_FIELDS = frozenset({
    "schema", "identity", "accepted_manifest_sha256", "generation_binding",
    "release_sha256", "capability", "source_seed", "source_each",
    "source_family_id", "source_binding_digest", "source_content_sha256",
    "teaching_enrichment_sha256", "rehearsal_plan_sha256",
    "rehearsal_rows_sha256", "content_identity", "visit_id",
    "candidate_step", "parent_optimizer_step", "executable_release",
    "source_rows", "prior_rows", "preservation_rows",
    "retention_support_rows", "rehearsal_bindings", "teaching_enrichment_rows",
})
_FRESH_REQUEST_FIELDS = frozenset({
    "fresh_support_rows", "fresh_support_binding", "fresh_support_depth_control",
    "fresh_support_unavailable_reason", "fresh_support_sha256",
})


def _invalid(reason: str):
    from bilqis_mlx.errors import ErrorBus, SCHOOL
    ErrorBus.raise_(SCHOOL.BAMF_RESOURCES.INVALID, reason=reason)


def _fingerprint(value) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _lesson_rows(selection, source_context, ordinal, enrichment_rows,
                 rehearsal_plan, rehearsal):
    offer = selection.offer
    if enrichment_rows is None:
        registry, graph = (
            getattr(source_context, "source_registry", None),
            getattr(source_context, "graph", None),
        )
        enrichment_rows = (() if registry is None or graph is None else
            optional_teaching_rows(
                getattr(source_context, "source_root", None), graph,
                source_context.release, registry, capability=offer.capability_id,
                seed=offer.source_seed, enabled=True))
    if rehearsal is None and rehearsal_plan is not None:
        rehearsal = materialize_rehearsal_rows(source_context, rehearsal_plan, ordinal)
    role_rows = {
        "prior": () if rehearsal is None else tuple(rehearsal.prior),
        "preservation": () if rehearsal is None else tuple(rehearsal.preservation),
        "retention_support": (
            () if rehearsal is None else tuple(rehearsal.retention_support)),
    }
    bindings = () if rehearsal is None else tuple(rehearsal.bindings)
    return tuple(enrichment_rows), role_rows, bindings


def _fresh_request_payload(fresh_support: FreshSupportSpecimen | None) -> dict:
    if fresh_support is None:
        return {}
    rows = tuple(fresh_support.rows)
    payload = {
        "rows": rows, "binding": fresh_support.binding,
        "depth_control": fresh_support.depth_control,
        "unavailable_reason": fresh_support.unavailable_reason,
    }
    return {
        "fresh_support_rows": list(rows),
        "fresh_support_binding": fresh_support.binding,
        "fresh_support_depth_control": fresh_support.depth_control,
        "fresh_support_unavailable_reason": fresh_support.unavailable_reason,
        "fresh_support_sha256": contract_digest(payload),
    }


def priority_source_request(
        selection, source_context, parent, ordinal: int, *, enrichment_rows=None,
        rehearsal_plan=None, rehearsal=None,
        fresh_support: FreshSupportSpecimen | None = None, target_batch=None) -> dict:
    """Bind one pure worker request to the exact accepted candidate step."""
    if type(ordinal) is not int or ordinal < 1:
        _invalid("BAMF_SOURCE_PREFETCH_STEP_INVALID")
    offer = selection.offer
    enrichment, role_rows, bindings = _lesson_rows(
        selection, source_context, ordinal, enrichment_rows, rehearsal_plan, rehearsal)
    fresh = _fresh_request_payload(fresh_support)
    rows, authority, seed = (
        (offer.rows(), offer.source_authority, offer.source_seed)
        if target_batch is None else target_batch)
    if (len(rows) != offer.source_each
            or any(row.get("capability") != offer.capability_id for row in rows)):
        _invalid("BAMF_SOURCE_PREFETCH_TARGET_SCOPE_DRIFT")
    content_binding = {
        "release_sha256": offer.release_sha256, "capability": offer.capability_id,
        "source_seed": seed, "source_each": offer.source_each,
        "source_family_id": authority.source_family_id,
        "source_binding_digest": offer.source_binding_digest,
        "source_content_sha256": authority.content_sha256,
        "teaching_enrichment_sha256": contract_digest(enrichment),
        "rehearsal_plan_sha256": None if rehearsal_plan is None else rehearsal_plan.identity,
        "rehearsal_rows_sha256": contract_digest({"rows": role_rows, "bindings": bindings}),
        **({"fresh_support_sha256": fresh["fresh_support_sha256"]} if fresh else {}),
    }
    content_identity = _fingerprint(content_binding)
    binding = {
        "schema": REQUEST_SCHEMA,
        "accepted_manifest_sha256": offer.accepted_manifest_sha256,
        "generation_binding": offer.generation_binding, **content_binding,
        "content_identity": content_identity,
        "visit_id": selection.visit.identity.visit_id, "candidate_step": ordinal,
        "parent_optimizer_step": parent.retained_state.optimizer_step,
    }
    return {
        **binding, "identity": _fingerprint(binding),
        "executable_release": source_context.release, "source_rows": rows,
        "prior_rows": list(role_rows["prior"]),
        "preservation_rows": list(role_rows["preservation"]),
        "retention_support_rows": list(role_rows["retention_support"]),
        "rehearsal_bindings": list(bindings),
        "teaching_enrichment_rows": list(enrichment), **fresh,
    }


def _validate_request_identity(request, has_fresh_support):
    fresh_key = (("fresh_support_sha256",) if has_fresh_support else ())
    binding_keys = (
        "schema", "accepted_manifest_sha256", "generation_binding", "release_sha256",
        "capability", "source_seed", "source_each", "source_family_id",
        "source_binding_digest", "source_content_sha256", "content_identity",
        "teaching_enrichment_sha256", "rehearsal_plan_sha256",
        "rehearsal_rows_sha256", "visit_id", "candidate_step", "parent_optimizer_step",
        *fresh_key,
    )
    content_keys = (
        "release_sha256", "capability", "source_seed", "source_each",
        "source_family_id", "source_binding_digest", "source_content_sha256",
        "teaching_enrichment_sha256", "rehearsal_plan_sha256",
        "rehearsal_rows_sha256", *fresh_key,
    )
    if request["identity"] != _fingerprint({key: request[key] for key in binding_keys}):
        _invalid("BAMF_SOURCE_PREFETCH_IDENTITY_INVALID")
    if request["content_identity"] != _fingerprint(
            {key: request[key] for key in content_keys}):
        _invalid("BAMF_SOURCE_PREFETCH_CONTENT_IDENTITY_INVALID")


def _validate_base_rows(request):
    release = request["executable_release"]
    if (release.release_sha256 != request["release_sha256"]
            or contract_digest(release.source_bindings.by_capability[
                request["capability"]]) != request["source_binding_digest"]):
        _invalid("BAMF_SOURCE_PREFETCH_RELEASE_DRIFT")
    rows = tuple(request["source_rows"])
    if (len(rows) != request["source_each"]
            or any(type(row) is not dict for row in rows)
            or source_content_digest(rows) != request["source_content_sha256"]):
        _invalid("BAMF_SOURCE_PREFETCH_SOURCE_DRIFT")
    enrichment = tuple(request["teaching_enrichment_rows"])
    if (any(type(row) is not dict for row in enrichment)
            or contract_digest(enrichment) != request["teaching_enrichment_sha256"]):
        _invalid("BAMF_SOURCE_PREFETCH_ENRICHMENT_DRIFT")
    roles = {name: tuple(request[name + "_rows"]) for name in (
        "prior", "preservation", "retention_support")}
    bindings = tuple(request["rehearsal_bindings"])
    if (any(type(row) is not dict for rows_ in roles.values() for row in rows_)
            or any(type(item) is not dict for item in bindings)
            or contract_digest({"rows": roles, "bindings": bindings})
            != request["rehearsal_rows_sha256"]):
        _invalid("BAMF_SOURCE_PREFETCH_REHEARSAL_DRIFT")
    return rows, enrichment, roles


def _fresh_packet_payload(request):
    rows = tuple(request["fresh_support_rows"])
    binding, control = request["fresh_support_binding"], request["fresh_support_depth_control"]
    reason = request["fresh_support_unavailable_reason"]
    if rows:
        valid = (len(rows) == 1 and type(rows[0]) is dict and isinstance(binding, dict)
                 and binding.get("role") == "fresh_support"
                 and binding.get("row_id") == rows[0].get("id")
                 and isinstance(control, str) and control and reason is None)
    else:
        realized_shallow = (
            binding is None and isinstance(control, str) and control and reason is None)
        unavailable = (
            binding is None and control is None and isinstance(reason, str) and reason)
        valid = realized_shallow or unavailable
    expected = contract_digest({
        "rows": rows, "binding": binding, "depth_control": control,
        "unavailable_reason": reason,
    })
    if not valid or expected != request["fresh_support_sha256"]:
        _invalid("BAMF_SOURCE_PREFETCH_FRESH_SUPPORT_DRIFT")
    return {
        "fresh_support": list(rows), "fresh_support_binding": binding,
        "fresh_support_depth_control": control,
        "fresh_support_unavailable_reason": reason,
    }


def prepare_priority_source_packet(request: dict) -> ImmutableSourcePacket:
    """Transport one already-authorized source batch without executing its provider."""
    if (not isinstance(request, dict)
            or set(request) not in (_BASE_REQUEST_FIELDS,
                                    _BASE_REQUEST_FIELDS | _FRESH_REQUEST_FIELDS)
            or FORBIDDEN_AUTHORITY_KEYS & set(request)
            or request.get("schema") != REQUEST_SCHEMA):
        _invalid("BAMF_SOURCE_PREFETCH_REQUEST_INVALID")
    has_fresh = _FRESH_REQUEST_FIELDS <= set(request)
    _validate_request_identity(request, has_fresh)
    rows, enrichment, roles = _validate_base_rows(request)
    fresh = _fresh_packet_payload(request) if has_fresh else {}
    return freeze_source_packet({
        "schema": SCHEMA, "identity": request["identity"], "fresh": list(rows),
        "prior": list(roles["prior"]), "preservation": list(roles["preservation"]),
        "retention_support": list(roles["retention_support"]),
        "teaching_enrichment_rows": list(enrichment), **fresh,
    })


__all__ = ("REQUEST_SCHEMA", "prepare_priority_source_packet", "priority_source_request")
