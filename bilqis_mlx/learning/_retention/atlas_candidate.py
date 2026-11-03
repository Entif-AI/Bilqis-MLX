"""B12.2 in-memory candidate custody over existing numerical owners.

Each optimizer step binds to owner-issued B09.2 execution provenance. A raw
caller mask is not an execution authority. B13/C publish retained
generations. New motif slots require materialized tensors and are rejected
here. Teacher observations stay outside the candidate state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_engram import INITIAL_MOTIF_CAPACITY, MotifBudget
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.atlas_plasticity import (
    PlasticityPolicy, advance_candidate_policy, next_update_mode,
)
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree, _adamw_update

from .atlas_execution_provenance import (
    StepExecutionProvenance, mask_digest, participation_digest,
)
from .atlas_participation import optimizer_participation_mask

STATE_SCHEMA = 'bilqis.mlx.candidate-state/provisional-v1'
TRANSACTION_SCHEMA = 'bilqis.mlx.candidate-transaction/provisional-v1'
STEP_PROOF_SCHEMA = 'bilqis.mlx.candidate-step-proof/v1'
DIGEST_HEX_LENGTH = 64
_TRANSACTION_ISSUER = object()
_RETAINED_STATE_ISSUER = object()


def _invalid():
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _is_digest(value) -> bool:
    """One lowercase hex digest identity, expressed as a domain contract."""
    return (isinstance(value, str) and len(value) == DIGEST_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in value))


def _is_genesis_allocations(snapshot: MotifAllocationSnapshot) -> bool:
    return (type(snapshot) is MotifAllocationSnapshot
            and not snapshot.manifest.slots
            and snapshot.manifest.capacity == INITIAL_MOTIF_CAPACITY
            and not snapshot.observed_uses
            and not snapshot.pending_keys
            and not snapshot.aliases)


@dataclass(frozen=True)
class CandidateState:
    """The inseparable proposed optimizer, allocation and policy state."""

    optimizer: AdamWStateTree
    policy: PlasticityPolicy
    allocations: MotifAllocationSnapshot
    optimizer_step: int
    step_proofs: tuple = ()
    schema_version: str = STATE_SCHEMA
    _issuance: object = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self):
        if (type(self.optimizer) is not AdamWStateTree
                or type(self.policy) is not PlasticityPolicy
                or type(self.allocations) is not MotifAllocationSnapshot
                or type(self.optimizer_step) is not int or self.optimizer_step < 0
                or type(self.step_proofs) is not tuple
                or any(type(proof) is not CandidateStepProof for proof in self.step_proofs)
                or any(proof.step_index != index + 1
                       for index, proof in enumerate(self.step_proofs))
                or self.schema_version != STATE_SCHEMA):
            _invalid()
        self.optimizer.validate()
        self.policy.validate()
        self.allocations.__post_init__()
        if (not _is_genesis_allocations(self.allocations)
                and getattr(self, '_issuance', None) is not _RETAINED_STATE_ISSUER):
            _invalid()
        for row in self.policy.row_ages:
            count = self.optimizer.update_counts.get(f'identity.bank.{row.bank_index}')
            if count is None or count.ndim != 1 or row.row_index >= count.shape[0]:
                _invalid()


def _load_retained_candidate_state_with_parts(
        bundle_root, *, expected_manifest_sha256: str):
    """Rehydrate retained state only from B13-validated immutable custody."""
    from bilqis_mlx.runtime.bamf_bundle.codec import _load_validated_bundle_parts

    parts = _load_validated_bundle_parts(
        bundle_root, expected_manifest_sha256=expected_manifest_sha256)
    state = object.__new__(CandidateState)
    for name, value in (
            ('optimizer', parts.numerical), ('policy', parts.policy),
            ('allocations', parts.motif), ('optimizer_step', parts.optimizer_step),
            ('schema_version', STATE_SCHEMA),
            ('_issuance', _RETAINED_STATE_ISSUER)):
        object.__setattr__(state, name, value)
    state.__post_init__()
    return state, parts


@dataclass(frozen=True)
class CandidateStepProof:
    """Owner-bound proof of one executed optimizer step.

    The proof records digests of the owner-issued execution provenance and its
    derived participation and mask. It never stores a caller mask mapping.
    """

    step_index: int
    provenance_sha256: str
    participation_sha256: str
    mask_sha256: str
    parameter_names: tuple[str, ...]
    loss_bearing: bool
    schema_version: str = STEP_PROOF_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.step_index) is not int or self.step_index < 1
                or not _is_digest(self.provenance_sha256)
                or not _is_digest(self.participation_sha256)
                or not _is_digest(self.mask_sha256)
                or type(self.parameter_names) is not tuple
                or self.parameter_names != tuple(sorted(set(self.parameter_names)))
                or any(not isinstance(name, str) or not name
                       for name in self.parameter_names)
                or type(self.loss_bearing) is not bool
                or self.schema_version != STEP_PROOF_SCHEMA):
            _invalid()

    @property
    def digest(self) -> str:
        """Content identity of one owner-bound step proof."""
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, init=False)
class CandidateTransaction:
    """One speculative branch; no method mutates or publishes its parent."""

    parent: CandidateState
    optimizer: AdamWStateTree
    allocations: MotifAllocationSnapshot
    teacher_requests_full: bool
    update_steps: int = 0
    step_proofs: tuple = ()
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
                or type(self.step_proofs) is not tuple
                or len(self.step_proofs) != self.update_steps
                or any(type(proof) is not CandidateStepProof for proof in self.step_proofs)
                or any(proof.step_index != index + 1
                       for index, proof in enumerate(self.step_proofs))
                or self.schema_version != TRANSACTION_SCHEMA):
            _invalid()
        self.parent.__post_init__()
        self.optimizer.validate()
        self.allocations.__post_init__()
        # Slot tensors are not materialized by this transaction slice.
        if (self.allocations is not self.parent.allocations
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


def _issue_transaction(parent, optimizer, teacher_requests_full, update_steps=0,
                       step_proofs=()):
    """Continue optimizer-only candidate state; allocation state is immutable here."""
    candidate = object.__new__(CandidateTransaction)
    for name, value in (
            ('parent', parent), ('optimizer', optimizer), ('allocations', parent.allocations),
            ('teacher_requests_full', teacher_requests_full), ('update_steps', update_steps),
            ('step_proofs', tuple(step_proofs)),
            ('schema_version', TRANSACTION_SCHEMA), ('_issuance', _TRANSACTION_ISSUER)):
        object.__setattr__(candidate, name, value)
    candidate.__post_init__()
    return candidate


def begin_candidate(parent: CandidateState, *, budget=None,
                    teacher_requests_full: bool = False) -> CandidateTransaction:
    """Begin optimizer-only work from one validated retained parent."""
    if type(parent) is not CandidateState or type(teacher_requests_full) is not bool:
        _invalid()
    parent.__post_init__()
    if budget is not None and type(budget) is not MotifBudget:
        _invalid()
    return _issue_transaction(parent, parent.optimizer, teacher_requests_full)


def candidate_step(candidate: CandidateTransaction, gradients, execution,
                   teacher_hparams, *, decay, loss_bearing: bool,
                   max_norm: float) -> CandidateTransaction:
    """Bind the step to owner-issued execution provenance, then run native AdamW.

    The mask comes from the B09.2 owner's provenance, never from a caller
    mapping. Counts identify actual participating rows, including
    numerical-zero gradients. No-loss and wholly frozen steps preserve the
    transaction object.
    """
    if type(candidate) is not CandidateTransaction:
        _invalid()
    candidate.__post_init__()
    if type(execution) is not StepExecutionProvenance:
        _invalid()
    update_mask = optimizer_participation_mask(
        execution.mask, candidate.optimizer.update_counts)
    optimizer = _adamw_update(
        candidate.optimizer, gradients, update_mask, teacher_hparams,
        decay=decay, loss_bearing=loss_bearing, max_norm=max_norm)
    if optimizer is candidate.optimizer:
        return candidate
    proof = CandidateStepProof(
        candidate.update_steps + 1, execution.digest,
        participation_digest(execution.participation), mask_digest(execution.mask),
        tuple(sorted(update_mask)), bool(loss_bearing))
    return _issue_transaction(candidate.parent, optimizer,
                              candidate.teacher_requests_full, candidate.update_steps + 1,
                              candidate.step_proofs + (proof,))


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
    step = candidate.parent.optimizer_step + candidate.update_steps
    if _is_genesis_allocations(candidate.allocations):
        return CandidateState(candidate.optimizer, policy, candidate.allocations, step,
                              tuple(candidate.step_proofs))
    state = object.__new__(CandidateState)
    for name, value in (
            ('optimizer', candidate.optimizer), ('policy', policy),
            ('allocations', candidate.allocations), ('optimizer_step', step),
            ('step_proofs', tuple(candidate.step_proofs)),
            ('schema_version', STATE_SCHEMA), ('_issuance', _RETAINED_STATE_ISSUER)):
        object.__setattr__(state, name, value)
    state.__post_init__()
    return state
