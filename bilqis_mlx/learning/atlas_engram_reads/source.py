"""Existing schema/grant evidence helpers for experimental reads."""
from __future__ import annotations

import hashlib


from bilqis_mlx.semantics.context_eligibility import ContextEligibility, SourceFrontier, TaskScope
from bilqis_mlx.semantics.frame_schema import FrameSchema


from .records import _invalid

def schema_source_handle(schema: FrameSchema) -> str:
    if type(schema) is not FrameSchema:
        _invalid()
    return f"source:motif-schema:{schema.identity}"


def schema_evidence_digest(schema: FrameSchema) -> str:
    if type(schema) is not FrameSchema:
        _invalid()
    return hashlib.sha256(schema.canonical_bytes()).hexdigest()


def _schema_grant_live(
    schema: FrameSchema, envelope: ContextEligibility,
    task: TaskScope, frontier: SourceFrontier,
) -> bool:
    grant = next(
        (item for item in frontier.grants
         if item.source_handle == schema_source_handle(schema)), None)
    return bool(
        grant is not None and not grant.revoked
        and grant.evidence_digest == schema_evidence_digest(schema)
        and grant.semantic_release == task.semantic_release
        and grant.source_regime == envelope.source_regime
        and grant.principal_id == task.principal_id
        and grant.tenant_id == task.tenant_id
        and task.purpose in grant.permitted_purposes
        and task.jurisdiction in grant.permitted_jurisdictions
        and task.scope in grant.permitted_scopes
        and grant.rights_epoch == frontier.rights_epoch
        and grant.correction_generation == frontier.correction_generation
        and grant.observed_at <= task.observed_frontier
        and grant.effective_from <= task.effective_time
        and (grant.effective_until is None
             or task.effective_time < grant.effective_until)
    )
