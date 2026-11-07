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

SourceSalience.__module__ = "bilqis_mlx.runtime.refinement_policy"
RefinementChoice.__module__ = "bilqis_mlx.runtime.refinement_policy"
RefinementSelection.__module__ = "bilqis_mlx.runtime.refinement_policy"
