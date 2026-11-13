"""Source-qualified B07.1 motif preparation over A03/A13 owner authority."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from bilqis_mlx.factory.adapters import RegisteredSourceAdapter
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.context_eligibility import (
    ApprovedContextProjection, ContextHold, ContextPolicy, SourceFrontier,
    TaskScope,
)
from .atlas_engram import (
    MotifBudget, MotifFrameInput, MotifManifest,
)
from .atlas_engram_identity import _SHA, _invalid
from .atlas_engram_source_batch import (
    SourceQualifiedMotifRequest, make_batch_parent_preparer,
)
from .atlas_engram_source_context import (
    _source_family as _source_family_impl,
    qualify_source_motif_context,
)
from .atlas_engram_transaction import (
    CandidateMotifSnapshot, MotifAllocationSnapshot,
    _prepare_candidate_motif_snapshot,
)

APPROVED_MOTIF_SCHEMA = "bilqis.motif-approved-candidate/v1"


def _new_approved_owner():
    issued = {}

    class _Issuance(NamedTuple):
        approved: object
        approved_context_digest: str
        candidate: CandidateMotifSnapshot
        candidate_digest: str
        schema_version: str

    def require(value):
        expected = issued.get(id(value))
        if (expected is None
                or expected.approved is not value
                or value.approved_context_digest != expected.approved_context_digest
                or value.candidate is not expected.candidate
                or value.candidate.digest != expected.candidate_digest
                or value.schema_version != expected.schema_version):
            _invalid("BAMF_MOTIF_APPROVED_CANDIDATE_INVALID")
        return value

    def issue(approved_context_digest, candidate):
        approved = object.__new__(ApprovedMotifCandidate)
        for name, value in (
                ("approved_context_digest", approved_context_digest),
                ("candidate", candidate), ("schema_version", APPROVED_MOTIF_SCHEMA)):
            object.__setattr__(approved, name, value)
        issued[id(approved)] = _Issuance(
            approved, approved_context_digest, candidate, candidate.digest,
            APPROVED_MOTIF_SCHEMA)
        approved.__post_init__()
        return approved

    return require, issue


@dataclass(frozen=True, init=False)
class ApprovedMotifCandidate:
    """Source-qualified projection/snapshot binding, not acceptance authority."""
    approved_context_digest: str
    candidate: CandidateMotifSnapshot
    schema_version: str = APPROVED_MOTIF_SCHEMA
    def __init__(self, *args, **kwargs):
        _invalid("BAMF_MOTIF_APPROVED_CANDIDATE_INVALID")

    def __post_init__(self) -> None:
        _require_approved_issued(self)
        if (not _SHA.fullmatch(self.approved_context_digest)
                or type(self.candidate) is not CandidateMotifSnapshot
                or self.schema_version != APPROVED_MOTIF_SCHEMA):
            _invalid("BAMF_MOTIF_APPROVED_CANDIDATE_INVALID")


def _require_approved_motif_candidate(value) -> None:
    if type(value) is not ApprovedMotifCandidate:
        _invalid("BAMF_MOTIF_APPROVED_CANDIDATE_INVALID")
    _require_approved_issued(value)
    value.__post_init__()


_require_approved_issued, _raw_issue_approved = _new_approved_owner()


def _source_family(adapter_id: str) -> str:
    """Preserve the established private owner path for B08 execution."""
    return _source_family_impl(adapter_id)


def source_qualified_motif_context(
    source_adapter: RegisteredSourceAdapter,
    row: dict,
    atlas_selection: AtlasArtifactSelection,
    *,
    source_root: str | Path,
    graph: dict,
    task_scope: TaskScope,
    source_frontier: SourceFrontier,
    policy: ContextPolicy,
    source_seed: int,
    source_each: int,
    source_profile_parameters: dict | None = None,
    course=None,
) -> tuple[
    ApprovedContextProjection, tuple[MotifFrameInput, ...], SourceFrontier,
] | ContextHold:
    """Stable public owner facade over source-context qualification."""
    return qualify_source_motif_context(
        source_adapter, row, atlas_selection, source_root=source_root,
        graph=graph, task_scope=task_scope, source_frontier=source_frontier,
        policy=policy, source_seed=source_seed, source_each=source_each,
        source_profile_parameters=source_profile_parameters, course=course,
    )


def _prepare_source_qualified_motifs_with_parent_impl(
    issue_approved,
    source_adapter: RegisteredSourceAdapter,
    row: dict,
    atlas_selection: AtlasArtifactSelection,
    *,
    source_root: str | Path,
    graph: dict,
    task_scope: TaskScope,
    source_frontier: SourceFrontier,
    policy: ContextPolicy,
    source_seed: int,
    source_each: int,
    budget: MotifBudget,
    parent: MotifAllocationSnapshot,
    source_profile_parameters: dict | None = None,
    course=None,
) -> tuple[ApprovedMotifCandidate, SourceFrontier] | ContextHold:
    """Pure B07 planning from source owners plus an already qualified parent."""
    if (type(atlas_selection) is not AtlasArtifactSelection
            or type(task_scope) is not TaskScope
            or type(source_frontier) is not SourceFrontier
            or type(policy) is not ContextPolicy
            or type(budget) is not MotifBudget
            or type(parent) is not MotifAllocationSnapshot):
        _invalid("BAMF_MOTIF_SOURCE_AUTHORITY_INVALID")
    parent.__post_init__()
    context = source_qualified_motif_context(
        source_adapter, row, atlas_selection, source_root=source_root,
        graph=graph, task_scope=task_scope, source_frontier=source_frontier,
        policy=policy, source_seed=source_seed, source_each=source_each,
        source_profile_parameters=source_profile_parameters, course=course)
    if isinstance(context, ContextHold):
        return context
    projection, qualified, issued_frontier = context
    if parent.manifest.semantic_release != task_scope.semantic_release:
        _invalid("BAMF_MOTIF_SOURCE_AUTHORITY_INVALID")
    candidate = _prepare_candidate_motif_snapshot(qualified, parent, budget)
    return issue_approved(projection.digest, candidate), issued_frontier


def _make_parent_preparer(issue_approved):
    def prepare(
        source_adapter: RegisteredSourceAdapter,
        row: dict,
        atlas_selection: AtlasArtifactSelection,
        **kwargs,
    ):
        return _prepare_source_qualified_motifs_with_parent_impl(
            issue_approved, source_adapter, row, atlas_selection, **kwargs)
    return prepare


_prepare_source_qualified_motifs_with_parent = _make_parent_preparer(
    _raw_issue_approved)
_prepare_source_qualified_motif_batch_with_parent = make_batch_parent_preparer(
    _raw_issue_approved, source_qualified_motif_context)
del _raw_issue_approved


def prepare_source_qualified_motifs(
    source_adapter: RegisteredSourceAdapter,
    row: dict,
    atlas_selection: AtlasArtifactSelection,
    *,
    source_root: str | Path,
    graph: dict,
    task_scope: TaskScope,
    source_frontier: SourceFrontier,
    policy: ContextPolicy,
    source_seed: int,
    source_each: int,
    budget: MotifBudget,
    source_profile_parameters: dict | None = None,
    course=None,
) -> tuple[ApprovedMotifCandidate, SourceFrontier] | ContextHold:
    """Replay source owners and plan only from an empty/genesis parent."""
    parent = MotifAllocationSnapshot(MotifManifest(task_scope.semantic_release))
    return _prepare_source_qualified_motifs_with_parent(
        source_adapter, row, atlas_selection,
        source_root=source_root, graph=graph, task_scope=task_scope,
        source_frontier=source_frontier, policy=policy,
        source_seed=source_seed, source_each=source_each, budget=budget,
        parent=parent, source_profile_parameters=source_profile_parameters,
        course=course,
    )
