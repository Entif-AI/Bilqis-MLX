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


POLICY_SCHEMA = "bilqis.mlx.refinement-selection/v1"
SALIENCE_SCHEMA = "bilqis.mlx.refinement-source-salience/v1"
PREFIX_INVENTORY_SCHEMA = "bilqis.mlx.refinement-prefix-inventory/v1"
MAX_SELECTED_FRAMES = 32
FRAMES_PER_QUOTA = 8
MAX_PASSES = 2
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value)


@dataclass(frozen=True)
class SourceSalience:
    """A source-owned ranking hint bound to one approved frame envelope.

    This is not an independent permission or gold label. Its issuer must be
    checked by the upstream source boundary, not inferred from this record.
    """

    frame_handle: str
    source_handle: str
    envelope_digest: str
    visible_at_prefix: int
    value: float
    schema_version: str = SALIENCE_SCHEMA

    def __post_init__(self) -> None:
        if (not _text(self.frame_handle)
                or not _text(self.source_handle)
                or not isinstance(self.envelope_digest, str)
                or not _DIGEST.fullmatch(self.envelope_digest)
                or type(self.visible_at_prefix) is not int
                or self.visible_at_prefix < 0
                or type(self.value) is not float
                or not math.isfinite(self.value)
                or self.schema_version != SALIENCE_SCHEMA):
            _invalid()


def salience_evidence_digest(witness: SourceSalience) -> str:
    """Content identity for a source-frontier grant to this exact signal."""
    if not isinstance(witness, SourceSalience):
        _invalid()
    payload = json.dumps(
        asdict(witness), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    )
    return hashlib.sha256((payload + "\n").encode("utf-8")).hexdigest()


def prefix_inventory_handle(source_id: str, p: int) -> str:
    """Stable handle that the A05 source owner must grant for this prefix."""
    if not _text(source_id) or type(p) is not int or p < 0:
        _invalid()
    return f"source:refinement-prefix:{source_id}:{p}"


def prefix_inventory_evidence_digest(compiled: CompiledFrameBatch) -> str:
    """Bind the complete p-local closure inventory, not a supplied subset."""
    if type(compiled) is not CompiledFrameBatch:
        _invalid()
    compiled.__post_init__()
    payload = json.dumps({
        "schema": PREFIX_INVENTORY_SCHEMA,
        "source_instance_id": compiled.source_instance_id,
        "prediction_boundary": compiled.visible_end,
        "semantic_release": compiled.semantic_release,
        "compiled_cache_key": compiled.cache_key,
        "context_digest": compiled.context_digest,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256((payload + "\n").encode("utf-8")).hexdigest()


def _verify_prefix_inventory(
    compiled: CompiledFrameBatch, task: TaskScope,
    frontier: SourceFrontier, policy: ContextPolicy,
) -> None:
    """A05's complete inventory needs its own source grant, not just atom grants."""
    handle = prefix_inventory_handle(
        compiled.source_instance_id, compiled.visible_end)
    grant = next(
        (item for item in frontier.grants if item.source_handle == handle),
        None)
    if (grant is None or grant.revoked
            or grant.evidence_digest != prefix_inventory_evidence_digest(compiled)
            or grant.semantic_release != task.semantic_release
            or grant.principal_id != task.principal_id
            or grant.tenant_id != task.tenant_id
            or grant.source_regime not in policy.allowed_regimes
            or task.purpose not in grant.permitted_purposes
            or task.jurisdiction not in grant.permitted_jurisdictions
            or task.scope not in grant.permitted_scopes
            or grant.rights_epoch != frontier.rights_epoch
            or grant.correction_generation != frontier.correction_generation
            or grant.observed_at > task.observed_frontier
            or grant.effective_from > task.effective_time
            or (grant.effective_until is not None
                and task.effective_time >= grant.effective_until)):
        _invalid()


@dataclass(frozen=True)
class RefinementChoice:
    frame_handle: str
    occurrence_id: str
    source_position: int
    role_matches: int
    salience: float
    passes: int
    cache_identity: tuple[str, int, str, str]


@dataclass(frozen=True)
class RefinementSelection:
    """A replayable selection proposal, not a transferable source credential."""
    input_generation: str
    prediction_boundary: int
    query_id: str
    approved_context_digest: str | None
    eligible_count: int
    quota: int
    selected: tuple[RefinementChoice, ...]
    remaining_frame_handles: tuple[str, ...]
    schema_version: str = POLICY_SCHEMA


def _sample_passes(
    run_seed: str, visit_id: str, prediction_boundary: int,
    query_id: str, occurrence_id: str,
) -> int:
    # Canonical length-delimited fields prevent ambiguous concatenations.
    message = json.dumps(
        (run_seed, visit_id, prediction_boundary, query_id, occurrence_id),
        separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(message).digest(), "big") % (MAX_PASSES + 1)


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
    return RefinementSelection(
        input_generation, p, query_id, projection.digest, len(visible),
        quota, tuple(choices),
        tuple(item.frame_handle for item in ranked[quota:]),
    )
