"""A09.5 adapter from pure atlas planning to the existing JIT proposal surface.

The adapter owns no source, staging, admission, or learning authority.  It binds
A09.1-A09.4 decisions to already verified Factory candidate artifacts and lets
the existing JIT gate re-check current learner evidence before emitting a
proposal.  Persisted staging and admission remain with their existing owners.
"""
from __future__ import annotations

from dataclasses import replace

from bilqis_mlx.errors import BilqisError
from .autonomy import AutonomyPlan
from .candidate_staging import StagedCandidate
from .jit_curriculum import ProposalDisposition, propose_curriculum_delta
from .atlas_frontier_closure import ClosureStatus, FrontierClosure
from .atlas_frontier_contracts import _fail
from .atlas_frontier_progress import plan_frontier_progress
from .atlas_frontier_progress_validation import (
    credited_obligation_keys,
    current_obligations,
)
from .atlas_frontier_progress_contracts import (
    FrontierStatus, StagedSelectionReceipt,
)
from .atlas_frontier_selection import (
    FrontierDeltaSelection, ranked_frontier_target,
    select_frontier_delta_for_projection, validate_frontier_selection,
)
from .atlas_frontier_selection_validation import TargetDeltaProjection
from . import candidate_realizations


from .atlas_delta_adapter_support import (
    AcceptedObligationCredit, AtlasCoverageEpoch, AtlasLearnerEvidence,
    _issue_accepted_obligation_credit, bind_realized_snapshot,
    bind_realized_snapshot_prevalidated,
    plan_frontier_progress_with_accepted_credit,
)


def _ready_rows(closure: FrontierClosure, semantic_id: str):
    rows = tuple(sorted(
        item for item in closure.candidates if item.semantic_id == semantic_id))
    return rows if rows and all(item.status is ClosureStatus.READY for item in rows) else ()


def _staged_for_projection(
    epoch: AtlasCoverageEpoch, projection: TargetDeltaProjection,
) -> StagedCandidate | None:
    try:
        expected_sense = candidate_realizations.realized_source_sense_id(
            projection.semantic_id)
    except ValueError:
        return None
    matches = []
    for staged in epoch.staged_candidates:
        transition = staged.successor.transition
        if transition is None:
            continue
        suffix = staged.successor.semantic_catalog[len(epoch.current_release.semantic_catalog):]
        if (staged.source_sense_id == expected_sense
                and staged.target_capability_id in projection.added_capability_ids
                and transition.added_capabilities == projection.added_capability_ids
                and tuple(suffix) == projection.introduced_semantic_ids):
            matches.append(staged)
    if len(matches) > 1:
        _fail("BAMF_PLANNER_ADAPTER_BINDING_AMBIGUOUS")
    return matches[0] if matches else None


def staged_selection_receipt(
    epoch: AtlasCoverageEpoch, selection: FrontierDeltaSelection,
    projection: TargetDeltaProjection, staged: StagedCandidate,
) -> StagedSelectionReceipt:
    """Build the existing A09.4/C07 handoff receipt for one persisted stage."""
    epoch.verify()
    staged.verify(epoch.candidate_frontier, epoch.current_release)
    validate_frontier_selection(
        epoch.snapshot, epoch.closure, selection,
        epoch.current_release, projection)
    provisional = StagedSelectionReceipt(
        selection, epoch.snapshot, projection, epoch.current_release,
        staged.successor, "0" * 64)
    receipt = replace(
        provisional, receipt_sha256=provisional.expected_digest())
    receipt.verify()
    return receipt


def _credited_requested_keys(coverage_epoch: AtlasCoverageEpoch) -> tuple[tuple[str, str], ...]:
    """Read compact authenticated historical credit before reranking."""
    if coverage_epoch.prior is None:
        return ()
    current = current_obligations(coverage_epoch.closure)
    return tuple(sorted(
        credited_obligation_keys(
            coverage_epoch.snapshot, coverage_epoch.closure,
            coverage_epoch.prior, current)))


def _accepted_requested_keys(
    coverage_epoch: AtlasCoverageEpoch,
) -> tuple[tuple[str, str], ...]:
    """Credit only exact obligation identities authenticated by B13 custody."""
    credit = coverage_epoch.accepted_credit
    if credit is None:
        return ()
    current = current_obligations(coverage_epoch.closure)
    return tuple(
        key for key in credit.obligation_keys
        if current.get(key[0]) == key[1]
    )


def next_atlas_delta(
    coverage_epoch: AtlasCoverageEpoch,
    learner_evidence: AtlasLearnerEvidence,
    existing_plan: AutonomyPlan,
) -> "AtlasDeltaScopeHandoff | FrontierStatus":
    """Return an authority-bound staged handoff or typed status without admission."""
    if (type(coverage_epoch) is not AtlasCoverageEpoch
            or type(learner_evidence) is not AtlasLearnerEvidence
            or type(existing_plan) is not AutonomyPlan):
        _fail("BAMF_PLANNER_ADAPTER_INPUT_INVALID")
    coverage_epoch.verify()

    # A persisted staged successor blocks reranking until the existing admission
    # owner resolves it.  A09.4 remains the authority for that replay decision.
    if (coverage_epoch.prior is not None
            and coverage_epoch.prior.pending_staged_successor_sha256 is not None):
        return plan_frontier_progress(
            coverage_epoch.snapshot, coverage_epoch.closure,
            prior=coverage_epoch.prior).status

    requested = tuple(sorted(set(
        (*_credited_requested_keys(coverage_epoch),
         *_accepted_requested_keys(coverage_epoch))
    )))
    try:
        semantic_id, rows = ranked_frontier_target(
            coverage_epoch.snapshot, coverage_epoch.closure, requested)
    except BilqisError as error:
        if error.context.get("reason") == "BAMF_PLANNER_NO_BOUNDED_READY_DELTA":
            if coverage_epoch.accepted_credit is not None:
                return plan_frontier_progress_with_accepted_credit(
                    coverage_epoch.snapshot, coverage_epoch.closure,
                    coverage_epoch.accepted_credit, prior=coverage_epoch.prior).status
            return plan_frontier_progress(
                coverage_epoch.snapshot, coverage_epoch.closure,
                prior=coverage_epoch.prior).status
        raise
    try:
        projection = candidate_realizations.project_authoritative_target(
            semantic_id, coverage_epoch.current_release, rows)
    except ValueError:
        return FrontierStatus.IMPLEMENTATION_UNCOVERED
    selection = select_frontier_delta_for_projection(
        coverage_epoch.snapshot, coverage_epoch.closure,
        coverage_epoch.current_release, projection, requested)
    progress = plan_frontier_progress(
        coverage_epoch.snapshot, coverage_epoch.closure, selection,
        current_release=coverage_epoch.current_release,
        selected_projection=projection, prior=coverage_epoch.prior)
    if progress.status is not FrontierStatus.PROPOSAL:
        return progress.status

    staged = _staged_for_projection(coverage_epoch, projection)
    if staged is None:
        return FrontierStatus.IMPLEMENTATION_UNCOVERED
    receipt = staged_selection_receipt(
        coverage_epoch, selection, projection, staged)
    deferred = tuple(sorted(
        item.candidate_id for item in coverage_epoch.candidate_frontier.candidates
        if item.candidate_id != staged.candidate_id))
    proposal = propose_curriculum_delta(
        coverage_epoch.candidate_frontier, coverage_epoch.current_release,
        learner_evidence.ledger, existing_plan,
        learner_evidence.checkpoint_sha256, learner_evidence.optimizer_step,
        candidate_bindings=(staged.binding,), deferred_candidate_ids=deferred)
    if proposal.disposition is not ProposalDisposition.PROPOSAL:
        return FrontierStatus.WAITING_FOR_EVIDENCE
    if (proposal.selected_candidate_ids != (staged.candidate_id,)
            or proposal.selected_successor_sha256 != staged.successor.release_sha256):
        _fail("BAMF_PLANNER_ADAPTER_SELECTION_DRIFT")
    from .atlas_delta_scope import build_atlas_delta_scope_handoff
    return build_atlas_delta_scope_handoff(
        coverage_epoch.candidate_frontier, receipt, staged, proposal)
