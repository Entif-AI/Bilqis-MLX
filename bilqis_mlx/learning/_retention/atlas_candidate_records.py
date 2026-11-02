"""Immutable B12.2 candidate records whose validity is replay-derived."""
from __future__ import annotations

from dataclasses import dataclass, field

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_engram import INITIAL_MOTIF_CAPACITY, MotifBudget
from bilqis_mlx.learning.atlas_engram_transaction import (
    MotifAllocationSnapshot, prepare_candidate_motif_snapshot,
)
from bilqis_mlx.learning.atlas_plasticity import (
    FOUNDATION_MODE, PlasticityPolicy, advance_candidate_policy, next_update_mode,
)
from bilqis_mlx.learning._retention.atlas_candidate_initialization import (
    CandidateInitialization, materialize_planned_motif_rows, same_optimizer,
)
from bilqis_mlx.runtime.atlas_optimizer import (
    AdamWStateTree, _adamw_update, _create_unbound_bamf_optimizer,
)
from bilqis_mlx.runtime.model_topology_v2 import validate_bamf_parameters

STATE_SCHEMA = 'bilqis.mlx.candidate-state/provisional-v1'
TRANSACTION_SCHEMA = 'bilqis.mlx.candidate-transaction/provisional-v1'
RESOLUTION_SCHEMA = 'bilqis.mlx.candidate-resolution/provisional-v1'


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


@dataclass(frozen=True)
class CandidateState:
    """The inseparable retained optimizer, allocation, policy, and decision state."""

    optimizer: AdamWStateTree
    policy: PlasticityPolicy
    allocations: MotifAllocationSnapshot
    optimizer_step: int
    initialization: CandidateInitialization
    parent: 'CandidateState | None' = field(default=None, repr=False, compare=False)
    resolution: 'CandidateResolution | None' = field(default=None, repr=False, compare=False)
    schema_version: str = STATE_SCHEMA

    def __post_init__(self):
        if (type(self.optimizer) is not AdamWStateTree
                or type(self.policy) is not PlasticityPolicy
                or type(self.allocations) is not MotifAllocationSnapshot
                or type(self.optimizer_step) is not int or self.optimizer_step < 0
                or type(self.initialization) is not CandidateInitialization
                or self.policy.mode != FOUNDATION_MODE
                or self.schema_version != STATE_SCHEMA):
            _invalid()
        self.optimizer.validate()
        self.policy.validate()
        self.allocations.__post_init__()
        self.initialization.__post_init__()
        if (self.initialization.extents.active_semantic_digest
                != self.allocations.manifest.semantic_release
                or self.initialization.extents.motif_page_count
                * INITIAL_MOTIF_CAPACITY != self.allocations.manifest.capacity):
            _invalid()
        validate_bamf_parameters(
            self.initialization.topology, self.initialization.extents,
            self.optimizer.parameters)
        if self.parent is None or self.resolution is None:
            self._validate_genesis()
        else:
            self._validate_descendant()
        for row in self.policy.row_ages:
            count = self.optimizer.update_counts.get(f'identity.bank.{row.bank_index}')
            if count is None or count.ndim != 1 or row.row_index >= count.shape[0]:
                _invalid()

    def _validate_genesis(self) -> None:
        if self.parent is not None or self.resolution is not None:
            _invalid()
        expected, _decay, _manifest = _create_unbound_bamf_optimizer(
            self.initialization.topology, self.initialization.extents,
            run_seed=self.initialization.run_seed)
        if (self.optimizer_step != 0 or self.policy != PlasticityPolicy()
                or self.allocations.manifest.slots or self.allocations.aliases
                or self.allocations.observed_uses or self.allocations.pending_keys
                or not same_optimizer(self.optimizer, expected)):
            _invalid()

    def _validate_descendant(self) -> None:
        if (type(self.parent) is not CandidateState
                or type(self.resolution) is not CandidateResolution):
            _invalid()
        transaction = self.resolution.candidate
        if (not self.resolution.accepted or transaction.update_steps == 0
                or transaction.parent is not self.parent
                or self.initialization is not self.parent.initialization):
            _invalid()
        self.parent.__post_init__()
        self.resolution.__post_init__()
        rows = tuple(row.identity for row in self.parent.policy.row_ages
                     if bool(transaction.optimizer.update_counts[
                         f'identity.bank.{row.bank_index}'][row.row_index]
                         > self.parent.optimizer.update_counts[
                             f'identity.bank.{row.bank_index}'][row.row_index]))
        expected_policy = advance_candidate_policy(
            self.parent.policy,
            teacher_requests_full=transaction.teacher_requests_full,
            accepted=True, participating_rows=rows)
        if (not same_optimizer(self.optimizer, transaction.optimizer)
                or self.allocations != transaction.allocations
                or self.optimizer_step != self.parent.optimizer_step + transaction.update_steps
                or self.policy != expected_policy):
            _invalid()


@dataclass(frozen=True)
class CandidateStepProof:
    gradients: dict
    update_mask: dict
    teacher_hparams: object
    decay: object
    loss_bearing: bool
    max_norm: float


@dataclass(frozen=True)
class CandidateTransaction:
    """One speculative branch; replay proves mechanics, not acceptance."""

    parent: CandidateState
    optimizer: AdamWStateTree
    allocations: MotifAllocationSnapshot
    teacher_requests_full: bool
    update_steps: int = 0
    frames: tuple = ()
    budget: MotifBudget = field(default_factory=lambda: MotifBudget(0))
    steps: tuple[CandidateStepProof, ...] = ()
    schema_version: str = TRANSACTION_SCHEMA

    def __post_init__(self):
        if (type(self.parent) is not CandidateState
                or type(self.optimizer) is not AdamWStateTree
                or type(self.allocations) is not MotifAllocationSnapshot
                or type(self.teacher_requests_full) is not bool
                or type(self.update_steps) is not int or self.update_steps < 0
                or type(self.frames) is not tuple or type(self.budget) is not MotifBudget
                or type(self.steps) is not tuple or self.update_steps != len(self.steps)
                or self.schema_version != TRANSACTION_SCHEMA):
            _invalid()
        self.parent.__post_init__()
        self.optimizer.validate()
        self.allocations.__post_init__()
        proposal = prepare_candidate_motif_snapshot(
            self.frames, self.parent.allocations, self.budget)
        expected = (materialize_planned_motif_rows(self.parent, proposal)
                    if proposal.view.plan.allocated else self.parent.optimizer)
        if self.allocations != proposal.proposed:
            _invalid()
        for step in self.steps:
            if type(step) is not CandidateStepProof:
                _invalid()
            updated = _adamw_update(
                expected, step.gradients, step.update_mask, step.teacher_hparams,
                decay=step.decay, loss_bearing=step.loss_bearing,
                max_norm=step.max_norm)
            if updated is expected:
                _invalid()
            expected = updated
        if not same_optimizer(self.optimizer, expected):
            _invalid()

    @property
    def update_mode(self) -> str:
        return next_update_mode(
            self.parent.policy, teacher_requests_full=self.teacher_requests_full)


@dataclass(frozen=True)
class CandidateResolution:
    """The retention owner's explicit accept/reject decision for one transaction."""

    candidate: CandidateTransaction
    accepted: bool
    schema_version: str = RESOLUTION_SCHEMA

    def __post_init__(self):
        if (type(self.candidate) is not CandidateTransaction
                or type(self.accepted) is not bool
                or self.schema_version != RESOLUTION_SCHEMA):
            _invalid()
        self.candidate.__post_init__()
