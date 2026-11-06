"""Speculative candidate transactions and accepted-state resolution."""
from __future__ import annotations
from dataclasses import dataclass, field
import mlx.core as mx
from bilqis_mlx.learning.atlas_engram import MotifBudget
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import advance_candidate_policy, next_update_mode
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree, _adamw_update
from ..atlas_execution_provenance import StepExecutionProvenance, mask_digest, participation_digest
from ..atlas_participation import optimizer_participation_mask
from .common import (LEGACY_STEP_PROOF_SCHEMA, STEP_PROOF_SCHEMA, RETAINED_STATE_ISSUER,
    STATE_SCHEMA, TRANSACTION_ISSUER, TRANSACTION_SCHEMA, invalid)
from .proofs import CandidateStepProof
from .state import CandidateState, _is_genesis_allocations

@dataclass(frozen=True, init=False)
class CandidateTransaction:
    """One speculative branch; no method mutates or publishes its parent."""

    parent: CandidateState
    optimizer: AdamWStateTree
    allocations: MotifAllocationSnapshot
    teacher_requests_full: bool
    update_steps: int = 0
    step_proofs: tuple = ()
    training_authorities: tuple = ()
    schema_version: str = TRANSACTION_SCHEMA
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        # Public construction/replacement cannot assert a completed transition.
        invalid()

    def __post_init__(self):
        if getattr(self, '_issuance', None) is not TRANSACTION_ISSUER:
            invalid()
        if (type(self.parent) is not CandidateState
                or type(self.optimizer) is not AdamWStateTree
                or type(self.allocations) is not MotifAllocationSnapshot
                or type(self.teacher_requests_full) is not bool
                or type(self.update_steps) is not int or self.update_steps < 0
                or type(self.step_proofs) is not tuple
                or len(self.step_proofs) != self.update_steps
                or type(self.training_authorities) is not tuple
                or len(self.training_authorities) != self.update_steps
                or any(type(proof) is not CandidateStepProof for proof in self.step_proofs)
                or any(proof.step_index != index + 1
                       for index, proof in enumerate(self.step_proofs))
                or self.schema_version != TRANSACTION_SCHEMA):
            invalid()
        self.parent.__post_init__()
        self.optimizer.validate()
        self.allocations.__post_init__()
        # Slot tensors are not materialized by this transaction slice.
        if (self.allocations is not self.parent.allocations
                or set(self.optimizer.parameters) != set(self.parent.optimizer.parameters)):
            invalid()
        for name, count in self.optimizer.update_counts.items():
            previous = self.parent.optimizer.update_counts[name]
            if (self.optimizer.parameters[name].shape != self.parent.optimizer.parameters[name].shape
                    or count.shape != previous.shape
                    or not bool(mx.all(count >= previous))
                    or not bool(mx.all(count - previous <= self.update_steps))):
                invalid()

    @property
    def update_mode(self) -> str:
        return next_update_mode(self.parent.policy, teacher_requests_full=self.teacher_requests_full)


def _issue_transaction(parent, optimizer, teacher_requests_full, update_steps=0,
                       step_proofs=(), training_authorities=()):
    """Continue optimizer-only candidate state; allocation state is immutable here."""
    candidate = object.__new__(CandidateTransaction)
    for name, value in (
            ('parent', parent), ('optimizer', optimizer), ('allocations', parent.allocations),
            ('teacher_requests_full', teacher_requests_full), ('update_steps', update_steps),
            ('step_proofs', tuple(step_proofs)),
            ('training_authorities', tuple(training_authorities)),
            ('schema_version', TRANSACTION_SCHEMA), ('_issuance', TRANSACTION_ISSUER)):
        object.__setattr__(candidate, name, value)
    candidate.__post_init__()
    return candidate


def begin_candidate(parent: CandidateState, *, budget=None,
                    teacher_requests_full: bool = False) -> CandidateTransaction:
    """Begin optimizer-only work from one validated retained parent."""
    if type(parent) is not CandidateState or type(teacher_requests_full) is not bool:
        invalid()
    parent.__post_init__()
    if budget is not None and type(budget) is not MotifBudget:
        invalid()
    return _issue_transaction(parent, parent.optimizer, teacher_requests_full)


def candidate_step(candidate: CandidateTransaction, gradients, execution,
                   teacher_hparams, *, decay, loss_bearing: bool,
                   max_norm: float, training_authority=None) -> CandidateTransaction:
    """Bind the step to owner-issued execution provenance, then run native AdamW.

    The mask comes from the B09.2 owner's provenance, never from a caller
    mapping. Counts identify actual participating rows, including
    numerical-zero gradients. No-loss and wholly frozen steps preserve the
    transaction object.
    """
    if type(candidate) is not CandidateTransaction:
        invalid()
    candidate.__post_init__()
    if type(execution) is not StepExecutionProvenance:
        invalid()
    custody = candidate.parent.custody
    if custody is None:
        invalid()
    from ..atlas_acceptance import candidate_identity_digest
    if (execution.run_id != custody.run_id
            or execution.generation != custody.generation + 1
            or (custody.manifest_sha256 is not None
                and execution.parent_manifest_sha256 != custody.manifest_sha256)
            or execution.topology_digest != custody.topology_digest
            or execution.extents_sha256 != custody.extents_digest
            or execution.parent_candidate_identity_sha256
            != candidate_identity_digest(candidate.parent)
            or execution.parent_optimizer_step != candidate.parent.optimizer_step
            or execution.candidate_step != candidate.update_steps + 1):
        invalid()
    update_mask = optimizer_participation_mask(
        execution.mask, candidate.optimizer.update_counts)
    optimizer = _adamw_update(
        candidate.optimizer, gradients, update_mask, teacher_hparams,
        decay=decay, loss_bearing=loss_bearing, max_norm=max_norm)
    if optimizer is candidate.optimizer:
        return candidate
    proof_args = dict(
        step_index=candidate.update_steps + 1,
        provenance_sha256=execution.digest,
        participation_sha256=participation_digest(execution.participation),
        mask_sha256=mask_digest(execution.mask),
        parameter_names=tuple(sorted(update_mask)),
        loss_bearing=bool(loss_bearing))
    if training_authority is None:
        proof = CandidateStepProof(
            **proof_args, schema_version=LEGACY_STEP_PROOF_SCHEMA)
    else:
        from bilqis_mlx.runtime.atlas_training_authority import BamfTrainingAuthority
        if type(training_authority) is not BamfTrainingAuthority:
            invalid()
        training_authority.__post_init__()
        proof = CandidateStepProof(
            **proof_args,
            source_release_sha256=training_authority.release_sha256,
            training_batch_sha256=training_authority.training_batch_sha256,
            target_capability_id=training_authority.delivery_capability,
            training_authority_sha256=training_authority.digest,
            source_family_id=training_authority.source_family_id,
            episode_id=training_authority.episode_id,
            schema_version=STEP_PROOF_SCHEMA)
    return _issue_transaction(
        candidate.parent, optimizer, candidate.teacher_requests_full,
        candidate.update_steps + 1, candidate.step_proofs + (proof,),
        candidate.training_authorities + (training_authority,))


def resolve_candidate(candidate: CandidateTransaction, *, accepted: bool) -> CandidateState:
    """Return all retained components together, or return the exact parent.

    accepted comes from the retention owner. This pure selection is neither a
    retention decision nor an accepted-generation/checkpoint publication grant.
    """
    if type(candidate) is not CandidateTransaction or type(accepted) is not bool:
        invalid()
    candidate.__post_init__()
    if not accepted or candidate.update_steps == 0:
        return candidate.parent
    rows = tuple(row.identity for row in candidate.parent.policy.row_ages
                 if bool(candidate.optimizer.update_counts[f'identity.bank.{row.bank_index}'][row.row_index]
                         > candidate.parent.optimizer.update_counts[f'identity.bank.{row.bank_index}'][row.row_index]))
    policy = advance_candidate_policy(
        candidate.parent.policy, teacher_requests_full=candidate.teacher_requests_full,
        accepted=True, participating_rows=rows)
    step = candidate.parent.optimizer_step + candidate.update_steps
    if _is_genesis_allocations(candidate.allocations):
        return CandidateState(candidate.optimizer, policy, candidate.allocations, step,
                              candidate.parent.custody,
                              tuple(candidate.step_proofs))
    state = object.__new__(CandidateState)
    for name, value in (
            ('optimizer', candidate.optimizer), ('policy', policy),
            ('allocations', candidate.allocations), ('optimizer_step', step),
            ('custody', candidate.parent.custody),
            ('step_proofs', tuple(candidate.step_proofs)),
            ('schema_version', STATE_SCHEMA), ('_issuance', RETAINED_STATE_ISSUER)):
        object.__setattr__(state, name, value)
    state.__post_init__()
    return state
