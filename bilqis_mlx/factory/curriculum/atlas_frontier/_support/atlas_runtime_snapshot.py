"""A09 snapshot binder for accepted executable runtime custody."""
from __future__ import annotations

from .atlas_frontier import _build_snapshot
from .atlas_frontier_contracts import PlannerBudget, _fail
from .atlas_delta_adapter import bind_realized_snapshot
from .candidate_frontier import CandidateFrontierRelease
from .candidate_staging import StagedCandidate
from .executable_release import ExecutableFactoryRelease
from .skos_curriculum import CurriculumCandidateSet
from bilqis_mlx.semantics.context_eligibility import ContextPolicy, SourceFrontier


def build_accepted_executable_snapshot(
    candidate: CurriculumCandidateSet,
    source_frontier: SourceFrontier,
    policy: ContextPolicy,
    candidate_frontier: CandidateFrontierRelease,
    current_release: ExecutableFactoryRelease,
    staged_candidates: tuple[StagedCandidate, ...],
    *,
    budget: PlannerBudget,
    admission_receipt_sha256: str | None = None,
    grade_labels: tuple[str, ...] = (),
):
    """Bind source/A08 truth to one accepted executable release without authority.

    This is the production counterpart to A09's pure snapshot constructor.  The
    caller must already possess accepted B13/C07 facts; this function only
    validates and projects them for planning and never stages or admits work.
    """
    if (type(candidate) is not CurriculumCandidateSet
            or type(source_frontier) is not SourceFrontier
            or type(policy) is not ContextPolicy
            or type(candidate_frontier) is not CandidateFrontierRelease
            or type(current_release) is not ExecutableFactoryRelease
            or type(staged_candidates) is not tuple
            or any(type(item) is not StagedCandidate for item in staged_candidates)
            or type(budget) is not PlannerBudget):
        _fail("BAMF_PLANNER_ACCEPTED_RUNTIME_INPUT_INVALID")
    current_release.verify()
    candidate_frontier.verify()
    for staged in staged_candidates:
        staged.verify(candidate_frontier, current_release)
    snapshot = _build_snapshot(
        candidate, source_frontier, policy,
        budget=budget,
        candidate_frontier_sha256=candidate_frontier.release_sha256,
        staged_release_sha256s=tuple(
            item.successor.release_sha256 for item in staged_candidates),
        admitted_release_sha256=current_release.release_sha256,
        admission_receipt_sha256=admission_receipt_sha256,
        grade_labels=grade_labels,
    )
    return bind_realized_snapshot(
        snapshot, candidate, candidate_frontier,
        current_release, staged_candidates)
