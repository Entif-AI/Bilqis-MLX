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
from .refinement_ranking import approved_salience, ranked_choices


def _validate_selection_inputs(frames, source_ast, compiler_config, task_scope,
                               source_frontier, policy, input_generation, query_id,
                               requested_roles, run_seed, visit_id, training,
                               explicit_member_question, unresolved_nested_query,
                               source_salience):
    if (not isinstance(frames, tuple)
            or any(not isinstance(frame, ContextEligibility) for frame in frames)
            or type(source_ast) is not StreamingAST
            or type(compiler_config) is not FrameCompilerConfig
            or not isinstance(task_scope, TaskScope)
            or not isinstance(source_frontier, SourceFrontier)
            or not isinstance(policy, ContextPolicy)
            or not all(_text(item) for item in (
                input_generation, query_id, run_seed, visit_id))
            or not isinstance(requested_roles, tuple)
            or any(not _text(role) for role in requested_roles)
            or len(set(requested_roles)) != len(requested_roles)
            or not isinstance(source_salience, tuple)
            or any(not isinstance(item, SourceSalience) for item in source_salience)
            or len({item.frame_handle for item in source_salience}) != len(source_salience)
            or not all(type(item) is bool for item in (
                training, explicit_member_question, unresolved_nested_query))):
        _invalid()
    p = task_scope.causal_prefix_end
    if (replace(compiler_config.task, causal_prefix_end=p) != task_scope
            or compiler_config.frontier != source_frontier
            or compiler_config.policy != policy):
        _invalid()
    if (explicit_member_question and not requested_roles):
        _invalid()
    handles = {item.frame_handle for item in frames}
    if len(handles) != len(frames) or any(
            item.frame_handle not in handles for item in source_salience):
        _invalid()
    return p


def select_prediction_refinements(
    *,
    frames: tuple[ContextEligibility, ...],
    source_ast: StreamingAST,
    compiler_config: FrameCompilerConfig,
    task_scope: TaskScope,
    source_frontier: SourceFrontier,
    policy: ContextPolicy,
    input_generation: str,
    query_id: str,
    requested_roles: tuple[str, ...],
    run_seed: str,
    visit_id: str,
    training: bool,
    explicit_member_question: bool,
    unresolved_nested_query: bool,
    source_salience: tuple[SourceSalience, ...] = (),
) -> RefinementSelection | ContextHold:
    """Select at most ceil(Fp/8) approved frames, capped at 32.

    V(p) is reconstructed from the complete A05 source AST and current
    compiler configuration, not merely a caller-supplied frame subset.
    The source compiler replays the exact prefix and A13 eligibility before
    the proposed visible frame inventory can determine the quota.
    """
    p = _validate_selection_inputs(
        frames, source_ast, compiler_config, task_scope, source_frontier, policy,
        input_generation, query_id, requested_roles, run_seed, visit_id, training,
        explicit_member_question, unresolved_nested_query, source_salience)

    visible = tuple(item for item in frames
                    if item.causal_prefix_end <= p
                    and item.frame.causal_prefix_end <= p
                    and item.frame.source_span.end <= p
                    and all(member.visible_at_prefix <= p for member in item.members))
    if not visible:
        compiled = compile_prefix(
            source_ast, p, task_scope.semantic_release, compiler_config)
        _verify_prefix_inventory(compiled, task_scope, source_frontier, policy)
        if any(item.kind is PositionKind.CLOSURE for item in compiled.positions):
            _invalid()
        return RefinementSelection(
            input_generation, p, query_id, None, 0, 0, (), ())

    projection = project_context(visible, task_scope, source_frontier, policy)
    if isinstance(projection, ContextHold):
        return projection
    if not isinstance(projection, ApprovedContextProjection):
        _invalid()
    compiled = compile_prefix(
        source_ast, p, task_scope.semantic_release, compiler_config)
    _verify_prefix_inventory(compiled, task_scope, source_frontier, policy)
    closure_handles = tuple(
        item.frame_handle for item in compiled.positions
        if item.kind is PositionKind.CLOSURE)
    if (len(closure_handles) != len(visible)
            or set(closure_handles) != {item.frame_handle for item in visible}
            or compiled.context_digest != projection.digest):
        _invalid()

    salience_by_handle = approved_salience(
        projection, visible, source_salience, source_frontier, task_scope, p)

    quota, choices, remaining = ranked_choices(
        visible, requested_roles, salience_by_handle, training, run_seed, visit_id,
        p, query_id, input_generation, explicit_member_question, unresolved_nested_query)
    return RefinementSelection(
        input_generation, p, query_id, projection.digest, len(visible),
        quota, choices, remaining,
    )
