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
_STATE_ISSUER = object()
_INITIALIZATION_ISSUER = object()
_TRANSACTION_ISSUER = object()


def _invalid():
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


@dataclass(frozen=True, init=False)
class CandidateInitialization:
    """B01 initialization authority carried by candidate-owned descendants."""

    topology: ModelTopologySpecV2
    extents: GenerationExtents
    run_seed: int
    schema_version: str = INITIALIZATION_SCHEMA
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        # A caller cannot merely assert which B01 initialization produced a tree.
        _invalid()

    def __post_init__(self):
        if (getattr(self, '_issuance', None) is not _INITIALIZATION_ISSUER
                or type(self.topology) is not ModelTopologySpecV2
                or type(self.extents) is not GenerationExtents
                or type(self.run_seed) is not int
                or self.schema_version != INITIALIZATION_SCHEMA):
            _invalid()


@dataclass(frozen=True, init=False)
class CandidateState:
    """The inseparable proposed optimizer, allocation and policy state."""

    optimizer: AdamWStateTree
    policy: PlasticityPolicy
    allocations: MotifAllocationSnapshot
    optimizer_step: int
    initialization: CandidateInitialization
    schema_version: str = STATE_SCHEMA
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        # Candidate custody begins only through bind_initial_candidate_state().
        _invalid()

    def __post_init__(self):
        if (getattr(self, '_issuance', None) is not _STATE_ISSUER
                or type(self.optimizer) is not AdamWStateTree
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
        for row in self.policy.row_ages:
            count = self.optimizer.update_counts.get(f'identity.bank.{row.bank_index}')
            if count is None or count.ndim != 1 or row.row_index >= count.shape[0]:
                _invalid()


def _issue_initialization(topology, extents, run_seed):
    binding = object.__new__(CandidateInitialization)
    for name, value in (
            ('topology', topology), ('extents', extents), ('run_seed', run_seed),
            ('schema_version', INITIALIZATION_SCHEMA),
            ('_issuance', _INITIALIZATION_ISSUER)):
        object.__setattr__(binding, name, value)
    binding.__post_init__()
    return binding


def _issue_state(optimizer, policy, allocations, optimizer_step, initialization):
    state = object.__new__(CandidateState)
    for name, value in (
            ('optimizer', optimizer), ('policy', policy), ('allocations', allocations),
            ('optimizer_step', optimizer_step), ('initialization', initialization),
            ('schema_version', STATE_SCHEMA), ('_issuance', _STATE_ISSUER)):
        object.__setattr__(state, name, value)
    state.__post_init__()
    return state


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
    binding = _issue_initialization(topology, extents, run_seed)
    return _issue_state(
        optimizer, PlasticityPolicy(), allocations, 0, binding)


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
        parent_manifest = self.parent.allocations.manifest
        candidate_manifest = self.allocations.manifest
        if (candidate_manifest.semantic_release != parent_manifest.semantic_release
                or candidate_manifest.capacity != parent_manifest.capacity
                or candidate_manifest.slots[:len(parent_manifest.slots)] != parent_manifest.slots
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
    return _issue_transaction(
        parent, optimizer, proposal.proposed, teacher_requests_full)


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
    return _issue_state(
        candidate.optimizer, policy, candidate.allocations,
        candidate.parent.optimizer_step + candidate.update_steps,
        candidate.parent.initialization)
