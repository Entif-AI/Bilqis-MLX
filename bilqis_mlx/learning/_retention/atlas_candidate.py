"""B12.2 in-memory candidate custody over existing numerical owners.

Masks remain caller-supplied. B11/B09 attest execution and eligibility; B13/C
publish retained generations. New motif slots require materialized tensors and
are rejected here. Teacher observations stay outside the candidate state.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_engram import MotifBudget
from bilqis_mlx.learning.atlas_engram_transaction import (
    MotifAllocationSnapshot, prepare_candidate_motif_snapshot,
)
from bilqis_mlx.learning.atlas_plasticity import (
    PlasticityPolicy, advance_candidate_policy, next_update_mode,
)
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree, _adamw_update

STATE_SCHEMA = 'bilqis.mlx.candidate-state/provisional-v1'
TRANSACTION_SCHEMA = 'bilqis.mlx.candidate-transaction/provisional-v1'
_TRANSACTION_ISSUER = object()


def _invalid():
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


@dataclass(frozen=True)
class CandidateState:
    """The inseparable proposed optimizer, allocation and policy state."""

    optimizer: AdamWStateTree
    policy: PlasticityPolicy
    allocations: MotifAllocationSnapshot
    optimizer_step: int
    schema_version: str = STATE_SCHEMA

    def __post_init__(self):
        if (type(self.optimizer) is not AdamWStateTree
                or type(self.policy) is not PlasticityPolicy
                or type(self.allocations) is not MotifAllocationSnapshot
                or type(self.optimizer_step) is not int or self.optimizer_step < 0
                or self.schema_version != STATE_SCHEMA):
            _invalid()
        self.optimizer.validate()
        self.policy.validate()
        self.allocations.__post_init__()
        for row in self.policy.row_ages:
            count = self.optimizer.update_counts.get(f'identity.bank.{row.bank_index}')
            if count is None or count.ndim != 1 or row.row_index >= count.shape[0]:
                _invalid()


@dataclass(frozen=True, init=False)
class CandidateTransaction:
    """One speculative branch; no method mutates or publishes its parent."""

    parent: CandidateState
    optimizer: AdamWStateTree
    allocations: MotifAllocationSnapshot
    teacher_requests_full: bool
    update_steps: int = 0
    schema_version: str = TRANSACTION_SCHEMA
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        # Public construction/replacement cannot assert a completed transition.
        _invalid()

    def __post_init__(self):
        if getattr(self, '_issuance', None) is not _TRANSACTION_ISSUER:
            _invalid()
        if (type(self.parent) is not CandidateState
                or type(self.optimizer) is not AdamWStateTree
                or type(self.allocations) is not MotifAllocationSnapshot
                or type(self.teacher_requests_full) is not bool
                or type(self.update_steps) is not int or self.update_steps < 0
                or self.schema_version != TRANSACTION_SCHEMA):
            _invalid()
        self.parent.__post_init__()
        self.optimizer.validate()
        self.allocations.__post_init__()
        # Slot tensors are not materialized by this transaction slice.
        if (self.allocations.manifest != self.parent.allocations.manifest
                or self.allocations.aliases != self.parent.allocations.aliases
                or set(self.optimizer.parameters) != set(self.parent.optimizer.parameters)):
            _invalid()
        for name, count in self.optimizer.update_counts.items():
            previous = self.parent.optimizer.update_counts[name]
            if (self.optimizer.parameters[name].shape != self.parent.optimizer.parameters[name].shape
                    or count.shape != previous.shape
                    or not bool(mx.all(count >= previous))
                    or not bool(mx.all(count - previous <= self.update_steps))):
                _invalid()

    @property
    def update_mode(self) -> str:
        return next_update_mode(self.parent.policy, teacher_requests_full=self.teacher_requests_full)


def _issue_transaction(parent, optimizer, allocations, teacher_requests_full, update_steps=0):
    """Only the two owner transition paths issue process-local candidate handles."""
    candidate = object.__new__(CandidateTransaction)
    for name, value in (
            ('parent', parent), ('optimizer', optimizer), ('allocations', allocations),
            ('teacher_requests_full', teacher_requests_full), ('update_steps', update_steps),
            ('schema_version', TRANSACTION_SCHEMA), ('_issuance', _TRANSACTION_ISSUER)):
        object.__setattr__(candidate, name, value)
    candidate.__post_init__()
    return candidate


def begin_candidate(parent: CandidateState, *, frames=(), budget=None,
                    teacher_requests_full: bool = False) -> CandidateTransaction:
    """Stage B07's pending keys/counters, without inventing initialized slots."""
    if type(parent) is not CandidateState or type(teacher_requests_full) is not bool:
        _invalid()
    parent.__post_init__()
    proposal = prepare_candidate_motif_snapshot(
        frames, parent.allocations, MotifBudget(0) if budget is None else budget)
    return _issue_transaction(parent, parent.optimizer, proposal.proposed, teacher_requests_full)


def candidate_step(candidate: CandidateTransaction, gradients, update_mask,
                   teacher_hparams, *, decay, loss_bearing: bool,
                   max_norm: float) -> CandidateTransaction:
    """Mask before clipping and delegate exact native AdamW to B12.1/B12.3.

    Counts identify actual participating rows, including numerical-zero
    gradients. No-loss and wholly frozen steps preserve the transaction object.
    """
    if type(candidate) is not CandidateTransaction:
        _invalid()
    candidate.__post_init__()
    optimizer = _adamw_update(
        candidate.optimizer, gradients, update_mask, teacher_hparams,
        decay=decay, loss_bearing=loss_bearing, max_norm=max_norm)
    if optimizer is candidate.optimizer:
        return candidate
    return _issue_transaction(candidate.parent, optimizer, candidate.allocations,
                                candidate.teacher_requests_full, candidate.update_steps + 1)


def resolve_candidate(candidate: CandidateTransaction, *, accepted: bool) -> CandidateState:
    """Return all retained components together, or return the exact parent.

    accepted comes from the retention owner. This pure selection is neither a
    retention decision nor an accepted-generation/checkpoint publication grant.
    """
    if type(candidate) is not CandidateTransaction or type(accepted) is not bool:
        _invalid()
    candidate.__post_init__()
    if not accepted or candidate.update_steps == 0:
        return candidate.parent
    rows = tuple(row.identity for row in candidate.parent.policy.row_ages
                 if bool(candidate.optimizer.update_counts[f'identity.bank.{row.bank_index}'][row.row_index]
                         > candidate.parent.optimizer.update_counts[f'identity.bank.{row.bank_index}'][row.row_index]))
    policy = advance_candidate_policy(
        candidate.parent.policy, teacher_requests_full=candidate.teacher_requests_full,
        accepted=True, participating_rows=rows)
    return CandidateState(candidate.optimizer, policy, candidate.allocations,
                          candidate.parent.optimizer_step + candidate.update_steps)
