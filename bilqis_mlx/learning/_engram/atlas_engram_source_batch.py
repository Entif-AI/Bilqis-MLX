"""Logical-batch B07 motif preparation over source-qualified row contexts."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from bilqis_mlx.factory.adapters import RegisteredSourceAdapter
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.context_eligibility import (
    ContextHold, ContextPolicy, SourceFrontier, TaskScope,
)

from .atlas_engram import MotifBudget
from .atlas_engram_identity import _invalid
from .atlas_engram_transaction import (
    MotifAllocationSnapshot, _prepare_candidate_motif_snapshot,
)


LOGICAL_BATCH_MIN_ROWS = 2


@dataclass(frozen=True)
class SourceQualifiedMotifRequest:
    """Source coordinates that B07 replays before owning one row's motif input."""

    source_adapter: RegisteredSourceAdapter
    row: dict
    atlas_selection: AtlasArtifactSelection
    source_root: Path
    graph: dict
    task_scope: TaskScope
    source_frontier: SourceFrontier
    policy: ContextPolicy
    source_seed: int
    source_each: int
    source_profile_parameters: dict | None = None
    course: object = None

    def __post_init__(self):
        if (not isinstance(self.row, dict)
                or type(self.atlas_selection) is not AtlasArtifactSelection
                or not isinstance(self.source_root, Path)
                or not isinstance(self.graph, dict)
                or type(self.task_scope) is not TaskScope
                or type(self.source_frontier) is not SourceFrontier
                or type(self.policy) is not ContextPolicy
                or type(self.source_seed) is not int or self.source_seed < 0
                or type(self.source_each) is not int or self.source_each < 1
                or (self.source_profile_parameters is not None
                    and not isinstance(self.source_profile_parameters, dict))):
            _invalid("BAMF_MOTIF_SOURCE_AUTHORITY_INVALID")


def _batch_context_digest(projections) -> str:
    payload = json.dumps(
        {
            "schema": "bilqis.mlx.b07-logical-batch-context/v1",
            "projections": tuple(projection.digest for projection in projections),
        },
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_batch_parent_preparer(issue_approved, source_context):
    """Compose row-qualified contexts into one candidate motif transition."""
    def prepare(requests, *, budget, parent):
        if (type(requests) is not tuple
                or len(requests) < LOGICAL_BATCH_MIN_ROWS
                or any(type(request) is not SourceQualifiedMotifRequest
                       for request in requests)
                or type(budget) is not MotifBudget
                or type(parent) is not MotifAllocationSnapshot):
            _invalid("BAMF_MOTIF_SOURCE_AUTHORITY_INVALID")
        parent.__post_init__()
        projections, qualified, frontiers = [], [], []
        for request in requests:
            request.__post_init__()
            if parent.manifest.semantic_release != request.task_scope.semantic_release:
                _invalid("BAMF_MOTIF_SOURCE_AUTHORITY_INVALID")
            context = source_context(
                request.source_adapter, request.row, request.atlas_selection,
                source_root=request.source_root, graph=request.graph,
                task_scope=request.task_scope, source_frontier=request.source_frontier,
                policy=request.policy, source_seed=request.source_seed,
                source_each=request.source_each,
                source_profile_parameters=request.source_profile_parameters,
                course=request.course,
            )
            if isinstance(context, ContextHold):
                return context
            projection, row_inputs, frontier = context
            projections.append(projection)
            qualified.extend(row_inputs)
            frontiers.append(frontier)
        candidate = _prepare_candidate_motif_snapshot(tuple(qualified), parent, budget)
        return issue_approved(
            _batch_context_digest(tuple(projections)), candidate), tuple(frontiers)
    return prepare
