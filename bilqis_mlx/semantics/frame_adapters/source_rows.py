"""A03/A13 bridge for exact source-owner row evidence."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from lib.ithkuil.src.skos.source_owner.row_witness import SourceRowByteWitness

from ..context_eligibility import (
    PUBLIC_FORMAL, ContextEligibility, ContextMember, SourceGrant,
    frame_evidence_digest, member_evidence_digest,
)
from .common import _adapter_fail
from ..frame_schema import SourceSpan, atomic_fallback


_SHA256_HEX_LENGTH = 64


@dataclass(frozen=True)
class SourceRowContext:
    """One source-owner row bound to A03 evidence plus matching A13 grants."""

    a01_source_bundle_id: str
    envelope: ContextEligibility
    grants: tuple[SourceGrant, ...]
    witness: SourceRowByteWitness


def _source_row_payload(
        witness: SourceRowByteWitness, semantic_id: str,
        a01_source_bundle_id: str) -> dict:
    return {
        "kind": "ithkuil-source-row",
        "semantic_id": semantic_id,
        "source_owner": witness.owner,
        "source_domain": witness.domain,
        "a01_source_bundle_id": a01_source_bundle_id,
        "source_reference": witness.source_reference,
        "table": witness.table,
        "key": witness.key,
        "record_sha256": witness.record_sha256,
        "record_start_byte": witness.record_start_byte,
        "record_end_byte": witness.record_end_byte,
        "values": dict(witness.values),
    }


def _source_row_grants(
        frame, member: ContextMember, frame_source: str, member_source: str, *,
        principal_id: str, tenant_id: str, purpose: str, semantic_release: str,
        jurisdiction: str, scope: str, rights_epoch: int,
        correction_generation: int, observed_at: int,
        effective_from: int) -> tuple[SourceGrant, ...]:
    common = dict(
        principal_id=principal_id,
        tenant_id=tenant_id,
        source_regime=PUBLIC_FORMAL,
        semantic_release=semantic_release,
        permitted_purposes=(purpose,),
        permitted_jurisdictions=(jurisdiction,),
        permitted_scopes=(scope,),
        rights_epoch=rights_epoch,
        correction_generation=correction_generation,
        observed_at=observed_at,
        effective_from=effective_from,
    )
    return tuple(sorted((
        SourceGrant(
            source_handle=frame_source,
            evidence_digest=frame_evidence_digest(frame),
            **common,
        ),
        SourceGrant(
            source_handle=member_source,
            evidence_digest=member_evidence_digest(frame, member),
            **common,
        ),
    ), key=lambda item: item.source_handle))


def _source_row_context(
    witness: SourceRowByteWitness,
    *,
    semantic_release: str,
    semantic_id: str,
    a01_source_bundle_id: str,
    principal_id: str,
    tenant_id: str,
    purpose: str,
    jurisdiction: str,
    scope: str,
    policy_epoch: int,
    rights_epoch: int,
    correction_generation: int,
    observed_at: int,
    effective_from: int,
    causal_prefix_end: int,
) -> SourceRowContext:
    """Bind exact row bytes without promoting the row into an admitted concept."""
    span = SourceSpan(0, 1)
    if (not isinstance(witness, SourceRowByteWitness)
            or not isinstance(a01_source_bundle_id, str)
            or len(a01_source_bundle_id) != _SHA256_HEX_LENGTH):
        _adapter_fail(
            "FRAME_SOURCE_ROW_WITNESS_REQUIRED",
            "source-row-context/v1", span, "<source-row>")
    # A03/A13 visibility is source-local, not an offset into a repository CSV.
    # Preserve absolute byte custody in the payload/witness, but expose this one
    # atomic row as the first source-local span so unrelated file ordering cannot
    # change causal visibility.
    if causal_prefix_end < span.end:
        _adapter_fail(
            "FRAME_SOURCE_ROW_CAUSAL_PREFIX_INVALID",
            "source-row-context/v1", span, "<source-row>")
    payload = _source_row_payload(witness, semantic_id, a01_source_bundle_id)
    frame = atomic_fallback(
        payload,
        source_instance_id=witness.source_reference,
        structural_path=(),
        source_span=span,
        parent_occurrence_id=None,
        causal_prefix_end=causal_prefix_end,
    )
    frame_handle = "source-row-frame:" + witness.record_sha256
    frame_source = witness.source_reference + "#frame"
    member_source = witness.source_reference + "#member"
    member = ContextMember("<atomic>", 0, member_source, span.end)
    envelope = ContextEligibility(
        frame_handle, frame, frame_source, (member,),
        principal_id, tenant_id, purpose, PUBLIC_FORMAL, semantic_release,
        jurisdiction, scope, PUBLIC_FORMAL, policy_epoch, rights_epoch,
        correction_generation, observed_at, effective_from, None,
        causal_prefix_end,
    )
    grants = _source_row_grants(
        frame, member, frame_source, member_source,
        principal_id=principal_id, tenant_id=tenant_id, purpose=purpose,
        semantic_release=semantic_release, jurisdiction=jurisdiction,
        scope=scope, rights_epoch=rights_epoch,
        correction_generation=correction_generation, observed_at=observed_at,
        effective_from=effective_from)
    return SourceRowContext(a01_source_bundle_id, envelope, grants, witness)


def source_row_context_digest(value: SourceRowContext) -> dict:
    """Plain canonical material for integration receipts and independent checks."""
    if not isinstance(value, SourceRowContext):
        _adapter_fail(
            "FRAME_SOURCE_ROW_CONTEXT_REQUIRED",
            "source-row-context/v1", SourceSpan(0, 1), "<source-row>")
    return {
        "envelope": asdict(value.envelope),
        "grants": [asdict(item) for item in value.grants],
        "witness": asdict(value.witness),
    }
