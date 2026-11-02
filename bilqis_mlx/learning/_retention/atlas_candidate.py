"""B12.2 in-memory candidate custody over existing numerical owners.

Masks remain caller-supplied. B11/B09 attest execution and eligibility; B13/C
publish retained generations. New motif slots require materialized tensors and
are rejected here. Teacher observations stay outside the candidate state.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_engram import (
    INITIAL_MOTIF_CAPACITY, MotifBudget, initialize_planned_motif_slot,
)
from bilqis_mlx.learning.atlas_engram_transaction import (
    MotifAllocationSnapshot, prepare_candidate_motif_snapshot,
)
from bilqis_mlx.learning.atlas_plasticity import (
    FOUNDATION_MODE, PlasticityPolicy, advance_candidate_policy, next_update_mode,
)
from bilqis_mlx.learning._retention.atlas_candidate_initialization import (
    verify_seed_from_untouched_b01_state,
)
from bilqis_mlx.runtime.atlas_optimizer import (
    AdamWStateTree, _adamw_update, _create_unbound_bamf_optimizer,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, validate_bamf_parameters,
)

STATE_SCHEMA = 'bilqis.mlx.candidate-state/provisional-v1'
TRANSACTION_SCHEMA = 'bilqis.mlx.candidate-transaction/provisional-v1'
INITIALIZATION_SCHEMA = 'bilqis.mlx.candidate-initialization-binding/v1'


def _invalid():
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


@dataclass(frozen=True)
class CandidateInitialization:
    """B01 initialization authority carried by candidate-owned descendants."""

    topology: ModelTopologySpecV2
    extents: GenerationExtents
    run_seed: int
    schema_version: str = INITIALIZATION_SCHEMA

    def __post_init__(self):
        if (type(self.topology) is not ModelTopologySpecV2
                or type(self.extents) is not GenerationExtents
                or type(self.run_seed) is not int
                or self.schema_version != INITIALIZATION_SCHEMA):
            _invalid()


@dataclass(frozen=True)
class CandidateState:
    """The inseparable proposed optimizer, allocation and policy state."""

    optimizer: AdamWStateTree
    policy: PlasticityPolicy
    allocations: MotifAllocationSnapshot
    optimizer_step: int
    initialization: CandidateInitialization
    parent: 'CandidateState | None' = field(default=None, repr=False, compare=False)
    transaction: 'CandidateTransaction | None' = field(default=None, repr=False, compare=False)
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
        if self.parent is None or self.transaction is None:
            if self.parent is not None or self.transaction is not None:
                _invalid()
            expected, _decay, _manifest = _create_unbound_bamf_optimizer(
                self.initialization.topology, self.initialization.extents,
                run_seed=self.initialization.run_seed)
            if (self.optimizer_step != 0 or self.policy != PlasticityPolicy()
                    or self.allocations.manifest.slots or self.allocations.aliases
                    or self.allocations.observed_uses or self.allocations.pending_keys
                    or not _same_optimizer(self.optimizer, expected)):
                _invalid()
        else:
            if (type(self.parent) is not CandidateState
                    or type(self.transaction) is not CandidateTransaction
                    or self.transaction.parent is not self.parent
                    or self.initialization is not self.parent.initialization):
                _invalid()
            self.parent.__post_init__()
            self.transaction.__post_init__()
            rows = tuple(row.identity for row in self.parent.policy.row_ages
                         if bool(self.transaction.optimizer.update_counts[
                             f'identity.bank.{row.bank_index}'][row.row_index]
                             > self.parent.optimizer.update_counts[
                                 f'identity.bank.{row.bank_index}'][row.row_index]))
            expected_policy = advance_candidate_policy(
                self.parent.policy,
                teacher_requests_full=self.transaction.teacher_requests_full,
                accepted=True, participating_rows=rows)
            if (not _same_optimizer(self.optimizer, self.transaction.optimizer)
                    or self.allocations != self.transaction.allocations
                    or self.optimizer_step != self.parent.optimizer_step + self.transaction.update_steps
                    or self.policy != expected_policy):
                _invalid()
        for row in self.policy.row_ages:
            count = self.optimizer.update_counts.get(f'identity.bank.{row.bank_index}')
            if count is None or count.ndim != 1 or row.row_index >= count.shape[0]:
                _invalid()


def _same_optimizer(left: AdamWStateTree, right: AdamWStateTree) -> bool:
    """Exact one-time B01 genesis comparison; later states inherit the binding."""
    left.validate()
    right.validate()
    for field in ('parameters', 'm', 'v', 'update_counts'):
        first, second = getattr(left, field), getattr(right, field)
        if set(first) != set(second):
            return False
        if any(not bool(mx.array_equal(first[name], second[name])) for name in first):
            return False
    return True


def bind_initial_candidate_state(
    optimizer: AdamWStateTree,
    allocations: MotifAllocationSnapshot,
    *,
    topology: ModelTopologySpecV2,
    extents: GenerationExtents,
    run_seed: int,
) -> CandidateState:
    """Enter B12 custody only from the exact complete B01 unbound genesis tree.

    The run seed is proven by replaying B01 initialization once at the custody
    boundary. Accepted candidate descendants carry that binding internally; a
    caller cannot later swap the seed while keeping the retained tree.
    """
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
            or not _same_optimizer(optimizer, expected)):
        _invalid()
    binding = CandidateInitialization(topology, extents, run_seed)
    return CandidateState(
        optimizer, PlasticityPolicy(), allocations, 0, binding)


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
    """One speculative branch; no method mutates or publishes its parent."""

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
                or type(self.frames) is not tuple
                or type(self.budget) is not MotifBudget
                or type(self.steps) is not tuple
                or self.update_steps != len(self.steps)
                or self.schema_version != TRANSACTION_SCHEMA):
            _invalid()
        self.parent.__post_init__()
        self.optimizer.validate()
        self.allocations.__post_init__()
        proposal = prepare_candidate_motif_snapshot(
            self.frames, self.parent.allocations, self.budget)
        expected = (_materialize_planned_motif_rows(self.parent, proposal)
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
        if not _same_optimizer(self.optimizer, expected):
            _invalid()

    @property
    def update_mode(self) -> str:
        return next_update_mode(self.parent.policy, teacher_requests_full=self.teacher_requests_full)


def _materialize_planned_motif_rows(parent, proposal):
    """Bind newly allocated in-page motif rows to B01 initialization exactly.

    This deliberately does not grow the parameter tree. Page growth changes the
    generation extents and remains outside this bounded B12.2 slice until its
    retained-generation owner can publish the enlarged tree atomically.
    """
    binding = parent.initialization
    if (type(binding) is not CandidateInitialization
            or type(binding.topology) is not ModelTopologySpecV2
            or type(binding.extents) is not GenerationExtents
            or type(binding.run_seed) is not int
            or binding.extents.active_semantic_digest != parent.allocations.manifest.semantic_release
            or binding.extents.motif_page_count * INITIAL_MOTIF_CAPACITY
            != parent.allocations.manifest.capacity
            or proposal.view.page_growth.added_pages != 0):
        _invalid()
    validate_bamf_parameters(
        binding.topology, binding.extents, parent.optimizer.parameters)
    verify_seed_from_untouched_b01_state(
        parent.optimizer, binding.topology, binding.extents, binding.run_seed)
    allocated = proposal.view.plan.allocated
    if not allocated:
        return parent.optimizer

    parameters = dict(parent.optimizer.parameters)
    first = dict(parent.optimizer.m)
    second = dict(parent.optimizer.v)
    counts = dict(parent.optimizer.update_counts)
    touched = {}
    for slot in allocated:
        page = slot.slot_id // INITIAL_MOTIF_CAPACITY
        row = slot.slot_id % INITIAL_MOTIF_CAPACITY
        name = f"motif.page.{page}"
        if name not in parameters or counts[name].shape != (INITIAL_MOTIF_CAPACITY,):
            _invalid()
        if name not in touched:
            touched[name] = (
                mx.array(parameters[name]), mx.array(first[name]),
                mx.array(second[name]), mx.array(counts[name]),
            )
        parameter, m, v, count = touched[name]
        parameter[row] = mx.array(initialize_planned_motif_slot(
            proposal.view, slot.slot_id, run_seed=binding.run_seed,
            topology=binding.topology, extents=binding.extents), dtype=mx.float32)
        m[row] = 0
        v[row] = 0
        count[row] = mx.array(0, dtype=mx.uint64)
    for name, values in touched.items():
        parameters[name], first[name], second[name], counts[name] = values
    mx.eval(parameters, first, second, counts)
    return AdamWStateTree(parameters, first, second, counts)


def begin_candidate(parent: CandidateState, *, frames=(), budget=None,
                    teacher_requests_full: bool = False) -> CandidateTransaction:
    """Stage B07 state and materialize new rows only through B01 initialization."""
    if type(parent) is not CandidateState or type(teacher_requests_full) is not bool:
        _invalid()
    parent.__post_init__()
    proposal = prepare_candidate_motif_snapshot(
        frames, parent.allocations, MotifBudget(0) if budget is None else budget)
    allocated = proposal.view.plan.allocated
    optimizer = (
        _materialize_planned_motif_rows(parent, proposal)
        if allocated else parent.optimizer)
    return CandidateTransaction(
        parent, optimizer, proposal.proposed, teacher_requests_full,
        frames=tuple(frames), budget=MotifBudget(0) if budget is None else budget)


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
    proof = CandidateStepProof(
        dict(gradients), dict(update_mask), teacher_hparams, decay,
        loss_bearing, max_norm)
    return CandidateTransaction(
        candidate.parent, optimizer, candidate.allocations,
        candidate.teacher_requests_full, candidate.update_steps + 1,
        candidate.frames, candidate.budget, candidate.steps + (proof,))


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
    return CandidateState(
        candidate.optimizer, policy, candidate.allocations,
        candidate.parent.optimizer_step + candidate.update_steps,
        candidate.parent.initialization, candidate.parent, candidate)
