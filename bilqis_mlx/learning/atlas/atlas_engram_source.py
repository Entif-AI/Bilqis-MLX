"""B07.1 source-gate integration probe, not a production admission authority.

The released A03 schema body and A13 grant issuer are not yet authenticated
by this candidate. Keep the probe private until those source owners expose
verifiable artifacts; do not wire it into neural or allocation production.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot
from bilqis_mlx.semantics.context_eligibility import (
    ContextEligibility, ContextHold, ContextPolicy, SourceFrontier, TaskScope,
    project_context,
)
from bilqis_mlx.semantics.frame_schema import (
    FrameInstance, FrameSchema, validate_frame_bindings,
)
from .atlas_engram import (
    CandidateMotifView, MotifBudget, MotifFrameInput, MotifManifest,
    _SHA, _invalid, prepare_motifs,
)

APPROVED_MOTIF_SCHEMA = "bilqis.motif-approved-candidate/v1"
SOURCE_AUTHORITY_FIELDS = 2  # Source graph and registered adapter identity.


@dataclass(frozen=True)
class ApprovedMotifCandidate:
    """Experimental projection/plan binding, not a source-admission credential."""
    approved_context_digest: str
    candidate: CandidateMotifView
    schema_version: str = APPROVED_MOTIF_SCHEMA

    def __post_init__(self) -> None:
        if (not _SHA.fullmatch(self.approved_context_digest)
                or type(self.candidate) is not CandidateMotifView
                or self.schema_version != APPROVED_MOTIF_SCHEMA):
            _invalid("BAMF_MOTIF_APPROVED_CANDIDATE_INVALID")


def _probe_approved_motifs(
    envelopes: tuple[ContextEligibility, ...],
    task: TaskScope,
    frontier: SourceFrontier,
    policy: ContextPolicy,
    schemas: tuple[FrameSchema, ...],
    snapshot: FrozenAtlasSnapshot,
    parent_manifest: MotifManifest,
    budget: MotifBudget,
    *,
    source_authorities: Mapping[str, tuple[dict | None, str | None]] | None = None,
) -> ApprovedMotifCandidate | ContextHold:
    """Exercise A03/A13 checks; caller-issued grants and schemas remain untrusted."""
    if (not isinstance(schemas, tuple)
            or any(type(item) is not FrameSchema for item in schemas)
            or type(task) is not TaskScope
            or type(frontier) is not SourceFrontier
            or type(policy) is not ContextPolicy
            or not isinstance(envelopes, tuple)
            or any(type(item) is not ContextEligibility for item in envelopes)
            or type(snapshot) is not FrozenAtlasSnapshot
            or type(parent_manifest) is not MotifManifest
            or type(budget) is not MotifBudget
            or snapshot.release_sha256 != task.semantic_release
            or parent_manifest.semantic_release != task.semantic_release):
        _invalid("BAMF_MOTIF_SOURCE_AUTHORITY_INVALID")
    keys = tuple((schema.schema_id, schema.revision) for schema in schemas)
    if len(set(keys)) != len(keys):
        _invalid("BAMF_MOTIF_SOURCE_SCHEMA_DUPLICATE")
    by_schema = dict(zip(keys, schemas))
    authorities = {} if source_authorities is None else source_authorities
    if (not isinstance(authorities, Mapping)
            or any(not isinstance(key, str) or not isinstance(value, tuple)
                   or len(value) != SOURCE_AUTHORITY_FIELDS for key, value in authorities.items())
            or set(authorities) - {item.frame_handle for item in envelopes}):
        _invalid("BAMF_MOTIF_SOURCE_AUTHORITY_INVALID")
    projection = project_context(envelopes, task, frontier, policy)
    if isinstance(projection, ContextHold):
        return projection
    qualified = []
    for envelope in projection.envelopes:
        frame = envelope.frame
        if not isinstance(frame, FrameInstance):
            # Atomic fallback is a valid context position, not a motif slot.
            continue
        schema = by_schema.get(
            (frame.frame_schema_id, frame.frame_schema_revision))
        if schema is None:
            _invalid("BAMF_MOTIF_SOURCE_SCHEMA_MISSING")
        graph, adapter_id = authorities.get(envelope.frame_handle, (None, None))
        validated = validate_frame_bindings(
            schema, snapshot, bindings=frame.bindings,
            source_span=frame.source_span,
            causal_prefix_end=frame.causal_prefix_end,
            declared_scope=schema.scope,
            source_graph=graph, source_adapter_id=adapter_id,
        )
        if validated != frame.bindings:
            _invalid("BAMF_MOTIF_SOURCE_BINDING_DRIFT")
        for binding in validated:
            concepts = ((binding.concept,) if binding.concept is not None
                        else binding.alternatives)
            for concept in concepts:
                abi = snapshot.abi_for_semantic(concept.semantic_id)
                if not abi.active:
                    _invalid("BAMF_MOTIF_SEMANTIC_NOT_ADMITTED")
        qualified.append(MotifFrameInput(frame, schema))
    return ApprovedMotifCandidate(
        projection.digest,
        prepare_motifs(tuple(qualified), parent_manifest, budget),
    )
