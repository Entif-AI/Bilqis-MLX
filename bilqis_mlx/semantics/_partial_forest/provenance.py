"""Provenance for source-owned partial forests."""
from __future__ import annotations
from .. import partial_visible_forest as _facade
from ..context_eligibility import ContextEligibility


from ..frame_schema import AtomicFrame, FrameInstance, FrameSchema
from .receipts import HiddenParentProvenance, PARTIAL_PARENT_SCHEMA


def _hidden_parent_provenance(
    child: FrameInstance | AtomicFrame,
    parent: FrameInstance | AtomicFrame,
    envelope: ContextEligibility,
    schemas: dict[tuple[str, int], FrameSchema],
) -> HiddenParentProvenance:
    if isinstance(parent, FrameInstance):
        schema = schemas.get(
            (parent.frame_schema_id, parent.frame_schema_revision))
        if schema is None:
            _facade._invalid("BAMF_PREFIX_PARTIAL_AUTHORITY_DRIFT")
        frame_authority = (
            parent.frame_schema_id,
            parent.frame_schema_revision,
            schema.scope,
        )
    else:
        frame_authority = ("<atomic>", 0, parent.ast_construct)
    provenance_digest = _facade.contract_digest((
        PARTIAL_PARENT_SCHEMA,
        parent.occurrence_id,
        parent.source_instance_id,
        parent.structural_path,
        (parent.source_span.start, parent.source_span.end),
        parent.parent_occurrence_id,
        parent.causal_prefix_end,
        frame_authority,
        envelope.frame_handle,
        envelope.source_handle,
        envelope.semantic_release,
        envelope.scope,
        envelope.source_regime,
        envelope.policy_epoch,
        envelope.rights_epoch,
        envelope.correction_generation,
    ))
    return HiddenParentProvenance(
        child.occurrence_id,
        parent.occurrence_id,
        envelope.frame_handle,
        provenance_digest,
    )
