"""Process-local issuance authority for B12.2 candidate transactions."""
from __future__ import annotations

import hashlib
from threading import RLock
from types import MappingProxyType
import weakref

import numpy as np

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_engram import MotifBudget
from bilqis_mlx.learning.atlas_engram_transaction import prepare_candidate_motif_snapshot
from bilqis_mlx.learning._retention.atlas_candidate_initialization import (
    materialize_planned_motif_rows,
)
from bilqis_mlx.learning._retention.atlas_candidate_records import (
    TRANSACTION_SCHEMA, CandidateResolution, CandidateState, CandidateStepProof,
    CandidateTransaction, _CandidateAttempt,
)
from bilqis_mlx.runtime.atlas_optimizer import _adamw_update


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _optimizer_fingerprint(state) -> str:
    digest = hashlib.sha256()
    for field_name in ('parameters', 'm', 'v', 'update_counts'):
        tree = getattr(state, field_name)
        for name in sorted(tree):
            value = np.asarray(tree[name])
            for part in (field_name, name, str(value.dtype), repr(value.shape)):
                digest.update(part.encode())
            digest.update(value.tobytes())
    return digest.hexdigest()


def _array_mapping_fingerprint(values) -> tuple:
    rows = []
    for name in sorted(values):
        value = np.asarray(values[name])
        rows.append((name, str(value.dtype), value.shape,
                     hashlib.sha256(value.tobytes()).hexdigest()))
    return tuple(rows)


def _proof_fingerprint(proof: CandidateStepProof) -> tuple:
    return (
        _array_mapping_fingerprint(proof.gradients),
        _array_mapping_fingerprint(proof.update_mask),
        repr(proof.teacher_hparams),
        tuple(sorted(proof.decay.items())),
        proof.loss_bearing,
        proof.max_norm,
    )


def _transaction_fingerprint(candidate: CandidateTransaction) -> tuple:
    return (
        _transaction_issuance_fingerprint(candidate),
        _optimizer_fingerprint(candidate.optimizer),
    )


def _transaction_issuance_fingerprint(candidate: CandidateTransaction) -> tuple:
    """Bind caller-visible transaction inputs; optimizer bytes are replay-checked."""
    return (
        id(candidate.parent), id(candidate.optimizer), candidate.allocations.digest,
        candidate.teacher_requests_full, id(candidate.attempt),
        candidate.update_steps, repr(candidate.frames), repr(candidate.budget),
        tuple(_proof_fingerprint(step) for step in candidate.steps),
        candidate.schema_version,
    )


def _clone_optimizer(state):
    copied = []
    for tree_name in ('parameters', 'm', 'v', 'update_counts'):
        copied.append({name: mx_array_copy(value)
                       for name, value in getattr(state, tree_name).items()})
    return type(state)(*copied)


def mx_array_copy(value):
    # MLX array construction gives candidate-owned copy-on-write storage without
    # synchronizing the complete tree through host NumPy.
    import mlx.core as mx
    return mx.array(value)


def _copy_array_mapping(values):
    return MappingProxyType({name: mx_array_copy(value)
                             for name, value in values.items()})


class _CandidateOwner:
    """Own attempts, exact transaction snapshots, and one-shot resolutions."""

    def __init__(self):
        self.lock = RLock()
        self.attempts = weakref.WeakSet()
        self.transactions = {}
        self.resolutions = {}

    def _forget(self, collection, key, item_ref) -> None:
        with self.lock:
            current = collection.get(key)
            if current is not None and current[0] is item_ref:
                collection.pop(key, None)

    def new_attempt(self):
        attempt = object.__new__(_CandidateAttempt)
        with self.lock:
            self.attempts.add(attempt)
        return attempt

    def transaction_is_issued(self, candidate) -> bool:
        if type(candidate) is not CandidateTransaction:
            return False
        with self.lock:
            current = self.transactions.get(id(candidate))
            return bool(current is not None and current[0]() is candidate
                        and current[1] == _transaction_issuance_fingerprint(candidate))

    def make_transaction(self, parent, optimizer, allocations,
                         teacher_requests_full, attempt, update_steps,
                         frames, budget, steps):
        candidate = object.__new__(CandidateTransaction)
        for name, value in (
            ('parent', parent), ('optimizer', optimizer), ('allocations', allocations),
            ('teacher_requests_full', teacher_requests_full), ('attempt', attempt),
            ('update_steps', update_steps), ('frames', frames), ('budget', budget),
            ('steps', steps), ('schema_version', TRANSACTION_SCHEMA),
        ):
            object.__setattr__(candidate, name, value)
        key = id(candidate)
        item_ref = weakref.ref(
            candidate, lambda ref, k=key: self._forget(self.transactions, k, ref))
        with self.lock:
            self.transactions[key] = (
                item_ref, _transaction_issuance_fingerprint(candidate))
        try:
            candidate.__post_init__()
        except Exception:
            self._forget(self.transactions, key, item_ref)
            raise
        return candidate

    def begin(self, parent, frames, budget, teacher_requests_full):
        if (type(parent) is not CandidateState or type(frames) is not tuple
                or type(budget) is not MotifBudget
                or type(teacher_requests_full) is not bool):
            _invalid()
        parent.__post_init__()
        proposal = prepare_candidate_motif_snapshot(frames, parent.allocations, budget)
        staged = (materialize_planned_motif_rows(parent, proposal)
                  if proposal.view.plan.allocated else parent.optimizer)
        optimizer = _clone_optimizer(staged)
        return self.make_transaction(
            parent, optimizer, proposal.proposed, teacher_requests_full,
            self.new_attempt(), 0, frames, budget, ())

    def advance(self, candidate, gradients, update_mask, teacher_hparams, *,
                decay, loss_bearing, max_norm):
        if type(candidate) is not CandidateTransaction:
            _invalid()
        candidate.__post_init__()
        key = id(candidate.attempt)
        with self.lock:
            current = self.resolutions.get(key)
            if current is not None and current[0]() is candidate.attempt:
                _invalid()
        optimizer = _adamw_update(
            candidate.optimizer, gradients, update_mask, teacher_hparams,
            decay=decay, loss_bearing=loss_bearing, max_norm=max_norm)
        if optimizer is candidate.optimizer:
            return candidate
        proof = CandidateStepProof(
            _copy_array_mapping(gradients), _copy_array_mapping(update_mask),
            teacher_hparams, MappingProxyType(dict(decay)),
            loss_bearing, max_norm)
        return self.make_transaction(
            candidate.parent, optimizer, candidate.allocations,
            candidate.teacher_requests_full, candidate.attempt,
            candidate.update_steps + 1, candidate.frames, candidate.budget,
            candidate.steps + (proof,))

    def issue_resolution(self, candidate, accepted: bool):
        if type(candidate) is not CandidateTransaction or type(accepted) is not bool:
            _invalid()
        candidate.__post_init__()
        key = id(candidate.attempt)
        with self.lock:
            current = self.resolutions.get(key)
            if current is not None and current[0]() is candidate.attempt:
                _invalid()
            resolution = CandidateResolution(candidate, accepted)
            attempt_ref = weakref.ref(
                candidate.attempt,
                lambda ref, k=key: self._forget(self.resolutions, k, ref))
            self.resolutions[key] = (
                attempt_ref, weakref.ref(candidate), _transaction_fingerprint(candidate),
                accepted, weakref.ref(resolution))
        return resolution

    def resolution_is_issued(self, resolution) -> bool:
        if type(resolution) is not CandidateResolution:
            return False
        with self.lock:
            current = self.resolutions.get(id(resolution.candidate.attempt))
            return bool(
                current is not None
                and current[0]() is resolution.candidate.attempt
                and current[1]() is resolution.candidate
                and current[2] == _transaction_fingerprint(resolution.candidate)
                and current[3] is resolution.accepted
                and current[4]() is resolution)


_candidate_owner = _CandidateOwner()
begin_candidate_transaction = _candidate_owner.begin
advance_candidate_transaction = _candidate_owner.advance
issue_candidate_resolution = _candidate_owner.issue_resolution
resolution_is_issued = _candidate_owner.resolution_is_issued
candidate_transaction_is_issued = _candidate_owner.transaction_is_issued
