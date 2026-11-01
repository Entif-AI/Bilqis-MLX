"""B06.2 prediction-local refinement policy over source-approved frames.

Selection is deterministic and does not mutate backbone, model or source state.
The source frontier and any salience witnesses must come from their owning
boundary; this module does not mint source grants or attest salience.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.context_eligibility import (
    ApprovedContextProjection, ContextEligibility, ContextHold, ContextPolicy,
    SourceFrontier, TaskScope, project_context,
)
from bilqis_mlx.semantics.frame_schema import FrameInstance
from bilqis_mlx.semantics.frame_compiler import (
    CompiledFrameBatch, FrameCompilerConfig, PositionKind, StreamingAST,
    compile_prefix,
)
from .refinement_contracts import (
    POLICY_SCHEMA,
    SALIENCE_SCHEMA,
    PREFIX_INVENTORY_SCHEMA,
    MAX_SELECTED_FRAMES,
    FRAMES_PER_QUOTA,
    MAX_PASSES,
    _DIGEST,
    _invalid,
    _text,
    SourceSalience,
    salience_evidence_digest,
    prefix_inventory_handle,
    prefix_inventory_evidence_digest,
    _verify_prefix_inventory,
    RefinementChoice,
    RefinementSelection,
    _sample_passes,
)


def approved_salience(projection, visible, source_salience, source_frontier, task_scope, p):
    approved = {item.frame_handle: item for item in projection.eligible.frames}
    salience_by_handle: dict[str, float] = {}
    grants = {item.source_handle: item for item in source_frontier.grants}
    occupied_handles = {
        handle for item in visible
        for handle in (item.source_handle,
                       *(member.source_handle for member in item.members))
    }
    source_envelopes = {item.frame_handle: item for item in visible}
    for witness in source_salience:
        # Ignore future-frame hints entirely: an earlier query is independent
        # of future observations, including their claimed salience.
        if witness.frame_handle not in approved:
            continue
        envelope = source_envelopes[witness.frame_handle]
        grant = grants.get(witness.source_handle)
        if (witness.envelope_digest
                != approved[witness.frame_handle].envelope_digest
                or witness.visible_at_prefix > p
                or witness.source_handle in occupied_handles
                or grant is None
                or grant.evidence_digest != salience_evidence_digest(witness)
                or grant.revoked
                or grant.semantic_release != task_scope.semantic_release
                or grant.source_regime != envelope.source_regime
                or grant.principal_id != task_scope.principal_id
                or grant.tenant_id != task_scope.tenant_id
                or task_scope.purpose not in grant.permitted_purposes
                or task_scope.jurisdiction not in grant.permitted_jurisdictions
                or task_scope.scope not in grant.permitted_scopes
                or grant.rights_epoch != source_frontier.rights_epoch
                or grant.correction_generation != source_frontier.correction_generation
                or grant.observed_at > task_scope.observed_frontier
                or grant.effective_from > task_scope.effective_time
                or (grant.effective_until is not None
                    and task_scope.effective_time >= grant.effective_until)):
            _invalid()
        salience_by_handle[witness.frame_handle] = witness.value
    return salience_by_handle


def ranked_choices(visible, requested_roles, salience_by_handle, training, run_seed,
                   visit_id, p, query_id, input_generation, explicit_member_question,
                   unresolved_nested_query):
    source_order = tuple(sorted(
        visible, key=lambda item: (
            item.frame.source_span.start,
            item.frame.source_span.end,
            item.frame.occurrence_id,
        )))
    position = {item.frame_handle: index for index, item in enumerate(source_order)}
    wanted = set(requested_roles)

    def rank(item: ContextEligibility) -> tuple[int, float, int]:
        roles = ({binding.role_id for binding in item.frame.bindings}
                 if isinstance(item.frame, FrameInstance) else set())
        return (-len(roles & wanted),
                -salience_by_handle.get(item.frame_handle, 0.0),
                position[item.frame_handle])

    ranked = tuple(sorted(visible, key=rank))
    quota = min(MAX_SELECTED_FRAMES, (len(visible) + FRAMES_PER_QUOTA - 1)
                // FRAMES_PER_QUOTA)
    choices = []
    for item in ranked[:quota]:
        frame = item.frame
        roles = ({binding.role_id for binding in frame.bindings}
                 if isinstance(frame, FrameInstance) else set())
        if training:
            passes = _sample_passes(
                run_seed, visit_id, p, query_id, frame.occurrence_id)
        elif unresolved_nested_query:
            passes = 2
        else:
            passes = int(explicit_member_question)
        choices.append(RefinementChoice(
            frame_handle=item.frame_handle,
            occurrence_id=frame.occurrence_id,
            source_position=position[item.frame_handle],
            role_matches=len(roles & wanted),
            salience=salience_by_handle.get(item.frame_handle, 0.0),
            passes=passes,
            cache_identity=(input_generation, p, query_id, frame.occurrence_id),
        ))
    return quota, tuple(choices), tuple(item.frame_handle for item in ranked[quota:])
