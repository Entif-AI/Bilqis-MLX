"""B12.2 in-memory candidate custody over existing numerical owners.

Transition mechanics are replayed independently from the retained decision.
B13/C still own durable generation publication and recovery authority.
"""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_engram import MotifBudget
from bilqis_mlx.learning.atlas_engram_transaction import (
    MotifAllocationSnapshot, prepare_candidate_motif_snapshot,
)
from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy, advance_candidate_policy
from bilqis_mlx.learning._retention.atlas_candidate_initialization import (
    CandidateInitialization, materialize_planned_motif_rows, same_optimizer,
)
from bilqis_mlx.learning._retention.atlas_candidate_records import (
    CandidateResolution, CandidateState, CandidateStepProof, CandidateTransaction,
)
from bilqis_mlx.runtime.atlas_optimizer import (
    AdamWStateTree, _adamw_update, _create_unbound_bamf_optimizer,
)
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def bind_initial_candidate_state(
    optimizer: AdamWStateTree,
    allocations: MotifAllocationSnapshot,
    *,
    topology: ModelTopologySpecV2,
    extents: GenerationExtents,
    run_seed: int,
) -> CandidateState:
    """Enter B12 custody only from the exact complete B01 unbound genesis tree."""
    if (type(optimizer) is not AdamWStateTree
            or type(allocations) is not MotifAllocationSnapshot
            or type(topology) is not ModelTopologySpecV2
            or type(extents) is not GenerationExtents
            or type(run_seed) is not int):
        _invalid()
    allocations.__post_init__()
    if (allocations.manifest.slots or allocations.aliases
            or allocations.observed_uses or allocations.pending_keys):
        _invalid()
    expected, _decay, manifest = _create_unbound_bamf_optimizer(
        topology, extents, run_seed=run_seed)
    if (manifest.get('run_seed') != run_seed
            or manifest.get('topology_digest') != topology.digest
            or manifest.get('generation_extents_digest') != extents.digest
            or not same_optimizer(optimizer, expected)):
        _invalid()
    return CandidateState(
        optimizer, PlasticityPolicy(), allocations, 0,
        CandidateInitialization(topology, extents, run_seed))


def begin_candidate(
    parent: CandidateState, *, frames=(), budget=None,
    teacher_requests_full: bool = False,
) -> CandidateTransaction:
    """Stage B07 state and materialize new rows only through B01 initialization."""
    if type(parent) is not CandidateState or type(teacher_requests_full) is not bool:
        _invalid()
    parent.__post_init__()
    resolved_budget = MotifBudget(0) if budget is None else budget
    proposal = prepare_candidate_motif_snapshot(
        frames, parent.allocations, resolved_budget)
    optimizer = (materialize_planned_motif_rows(parent, proposal)
                 if proposal.view.plan.allocated else parent.optimizer)
    return CandidateTransaction(
        parent, optimizer, proposal.proposed, teacher_requests_full,
        frames=tuple(frames), budget=resolved_budget)


def candidate_step(
    candidate: CandidateTransaction, gradients, update_mask, teacher_hparams,
    *, decay, loss_bearing: bool, max_norm: float,
) -> CandidateTransaction:
    """Mask before clipping and delegate exact native AdamW to B12.1/B12.3."""
    if type(candidate) is not CandidateTransaction:
        _invalid()
    candidate.__post_init__()
    optimizer = _adamw_update(
        candidate.optimizer, gradients, update_mask, teacher_hparams,
        decay=decay, loss_bearing=loss_bearing, max_norm=max_norm)
    if optimizer is candidate.optimizer:
        return candidate
    proof = CandidateStepProof(
        dict(gradients), dict(update_mask), teacher_hparams, decay,
        loss_bearing, max_norm)
    return CandidateTransaction(
        candidate.parent, optimizer, candidate.allocations,
        candidate.teacher_requests_full, candidate.update_steps + 1,
        candidate.frames, candidate.budget, candidate.steps + (proof,))


def resolve_candidate(candidate: CandidateTransaction, *, accepted: bool) -> CandidateState:
    """Apply the retention owner's decision or return the exact parent."""
    if type(candidate) is not CandidateTransaction or type(accepted) is not bool:
        _invalid()
    resolution = CandidateResolution(candidate, accepted)
    if not resolution.accepted or candidate.update_steps == 0:
        return candidate.parent
    rows = tuple(row.identity for row in candidate.parent.policy.row_ages
                 if bool(candidate.optimizer.update_counts[
                     f'identity.bank.{row.bank_index}'][row.row_index]
                     > candidate.parent.optimizer.update_counts[
                         f'identity.bank.{row.bank_index}'][row.row_index]))
    policy = advance_candidate_policy(
        candidate.parent.policy,
        teacher_requests_full=candidate.teacher_requests_full,
        accepted=True, participating_rows=rows)
    return CandidateState(
        candidate.optimizer, policy, candidate.allocations,
        candidate.parent.optimizer_step + candidate.update_steps,
        candidate.parent.initialization, candidate.parent, resolution)
