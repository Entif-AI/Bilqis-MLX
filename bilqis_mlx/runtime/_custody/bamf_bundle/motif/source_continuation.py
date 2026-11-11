"""B13-owned source continuation from immutable retained-generation custody."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from bilqis_mlx.data_plane import SHA256_HEX_LENGTH
from bilqis_mlx.learning.atlas_engram_source import (
    ApprovedMotifCandidate, _require_approved_motif_candidate,
    _prepare_source_qualified_motifs_with_parent,
)
from bilqis_mlx.semantics.context_eligibility import ContextHold
from ..codec import load_bamf_bundle
from ..records import invalid


def _new_continuation_owner():
    issued = {}

    def require(value):
        expected = issued.get(id(value))
        if (expected is None
                or expected[0] is not value
                or value.approved is not expected[1]
                or value.parent_manifest_sha256 != expected[2]
                or value.parent_extents_sha256 != expected[3]
                or value.parent_allocation_sha256 != expected[4]):
            invalid("BAMF_MOTIF_SOURCE_CONTINUATION_INVALID")
        return value

    def issue(approved, student, manifest_sha256):
        continuation = object.__new__(SourceQualifiedMotifContinuation)
        for name, value in (
                ("approved", approved), ("parent_manifest_sha256", manifest_sha256),
                ("parent_extents_sha256", student.extents.digest),
                ("parent_allocation_sha256", student.retained_state.allocations.digest)):
            object.__setattr__(continuation, name, value)
        issued[id(continuation)] = (
            continuation, approved, manifest_sha256, student.extents.digest,
            student.retained_state.allocations.digest)
        continuation.__post_init__()
        return continuation

    return require, issue


@dataclass(frozen=True, init=False)
class SourceQualifiedMotifContinuation:
    """B13 seal joining source-qualified B07 planning to one exact parent."""

    approved: ApprovedMotifCandidate
    parent_manifest_sha256: str
    parent_extents_sha256: str
    parent_allocation_sha256: str
    def __init__(self, *args, **kwargs):
        invalid("BAMF_MOTIF_SOURCE_CONTINUATION_INVALID")

    def __post_init__(self):
        _require_continuation_issued(self)
        _require_approved_motif_candidate(self.approved)
        if any(_required_manifest_sha256(value) != value for value in (
                    self.parent_manifest_sha256, self.parent_extents_sha256,
                    self.parent_allocation_sha256)):
            invalid("BAMF_MOTIF_SOURCE_CONTINUATION_INVALID")


def _require_source_qualified_continuation(value):
    if type(value) is not SourceQualifiedMotifContinuation:
        invalid("BAMF_MOTIF_SOURCE_CONTINUATION_INVALID")
    _require_continuation_issued(value)
    value.__post_init__()
    return value


_require_continuation_issued, _raw_issue_continuation = _new_continuation_owner()


def _required_manifest_sha256(value: object) -> str:
    if (type(value) is not str or len(value) != SHA256_HEX_LENGTH
            or any(character not in "0123456789abcdef" for character in value)):
        invalid()
    return value


def continue_source_qualified_motifs_from_bundle(
        source_adapter, row, atlas_selection, *, retained_bundle_root: str | Path,
        expected_manifest_sha256: str, source_root, graph, task_scope,
        source_frontier, policy, source_seed: int, source_each: int, budget,
        source_profile_parameters=None, course=None):
    """Continue B07 planning only from one exact custody-validated bundle."""
    expected_manifest_sha256 = _required_manifest_sha256(expected_manifest_sha256)
    student = load_bamf_bundle(
        Path(retained_bundle_root),
        expected_manifest_sha256=expected_manifest_sha256,
    )
    return _prepare_source_qualified_motifs_with_parent(
        source_adapter, row, atlas_selection,
        source_root=source_root, graph=graph, task_scope=task_scope,
        source_frontier=source_frontier, policy=policy,
        source_seed=source_seed, source_each=source_each, budget=budget,
        parent=student.retained_state.allocations,
        source_profile_parameters=source_profile_parameters, course=course,
    )


def _seal_source_qualified_motifs_from_bundle(
        issue_continuation,
        source_adapter, row, atlas_selection, *, retained_bundle_root: str | Path,
        expected_manifest_sha256: str, source_root, graph, task_scope,
        source_frontier, policy, source_seed: int, source_each: int, budget,
        source_profile_parameters=None, course=None):
    """Source-plan and seal one B07 proposal to the exact B13 parent identity."""
    expected_manifest_sha256 = _required_manifest_sha256(expected_manifest_sha256)
    student = load_bamf_bundle(
        Path(retained_bundle_root), expected_manifest_sha256=expected_manifest_sha256)
    result = _prepare_source_qualified_motifs_with_parent(
        source_adapter, row, atlas_selection,
        source_root=source_root, graph=graph, task_scope=task_scope,
        source_frontier=source_frontier, policy=policy,
        source_seed=source_seed, source_each=source_each, budget=budget,
        parent=student.retained_state.allocations,
        source_profile_parameters=source_profile_parameters, course=course)
    if isinstance(result, ContextHold):
        return result
    approved, frontier = result
    return issue_continuation(approved, student, expected_manifest_sha256), frontier


def _make_source_sealer(issue_continuation):
    def seal(source_adapter, row, atlas_selection, **kwargs):
        return _seal_source_qualified_motifs_from_bundle(
            issue_continuation, source_adapter, row, atlas_selection, **kwargs)
    return seal


seal_source_qualified_motifs_from_bundle = _make_source_sealer(
    _raw_issue_continuation)
del _raw_issue_continuation


def stage_source_qualified_motif_allocation(
        run_dir: str | Path, transaction, continuation: SourceQualifiedMotifContinuation):
    """Materialize one exact sealed B07 proposal into speculative B12 custody."""
    from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
    from bilqis_mlx.learning.atlas_candidate import CandidateTransaction
    from bilqis_mlx.learning._atlas_candidate.transaction import (
        _stage_candidate_motif_allocation,
    )
    from ..admission import load_accepted_generation

    continuation = _require_source_qualified_continuation(continuation)
    if type(transaction) is not CandidateTransaction:
        invalid("BAMF_MOTIF_SOURCE_CONTINUATION_INVALID")
    parent = load_accepted_generation(Path(run_dir))
    custody = transaction.parent.custody
    if (custody is None
            or parent.run_identity is None
            or continuation.parent_manifest_sha256 != custody.manifest_sha256
            or continuation.parent_manifest_sha256 != parent.retained_state.custody.manifest_sha256
            or continuation.parent_extents_sha256 != parent.extents.digest
            or continuation.parent_extents_sha256 != custody.extents_digest
            or continuation.parent_allocation_sha256 != parent.retained_state.allocations.digest
            or continuation.parent_allocation_sha256 != transaction.parent.allocations.digest
            or candidate_identity_digest(transaction.parent)
            != candidate_identity_digest(parent.retained_state)):
        invalid("BAMF_MOTIF_SOURCE_CONTINUATION_INVALID")
    approved = continuation.approved
    from bilqis_mlx.runtime.model_topology_v2 import b01_generation_extents
    proposed = approved.candidate.proposed
    candidate_extents = b01_generation_extents(
        semantic_abi=parent.semantic_abi,
        compiler_features=parent.compiler_features,
        motif_page_count=proposed.manifest.capacity // 16384,
        motif_key_map_digest=proposed.manifest.digest)
    return _stage_candidate_motif_allocation(
        transaction, continuation, spec=parent.topology,
        parent_extents=parent.extents, candidate_extents=candidate_extents,
        run_seed=parent.run_identity.run_seed)
