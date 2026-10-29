"""Private numerical AdamW counts; full-model candidate custody remains separate.

No durable student, participation policy, clipping policy, generation publication
or historical optimizer migration is implemented by this numerical seam.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

import mlx.core as mx
import mlx.optimizers as optim
import numpy as np

from bilqis_mlx.errors import ErrorBus, SCHOOL


ROW_COUNT_RANK = 1
ADAM_MOMENT_COUNT = 2
UINT64_MAX = int(np.iinfo(np.uint64).max)
STATE_SCHEMA = "bilqis.mlx.adamw-count-state/provisional-v1"


def _invalid():
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True)
class AdamWHyperparameters:
    """Exact supplied teacher values; this record makes no policy selection."""

    learning_rate: float
    betas: tuple[float, float]
    eps: float
    weight_decay: float

    def __post_init__(self):
        if (not _finite_number(self.learning_rate) or self.learning_rate <= 0 or
                type(self.betas) is not tuple or len(self.betas) != ADAM_MOMENT_COUNT or
                any(not _finite_number(beta) or not 0 <= beta < 1 for beta in self.betas) or
                not _finite_number(self.eps) or self.eps <= 0 or
                not _finite_number(self.weight_decay) or self.weight_decay < 0):
            _invalid()


@dataclass(frozen=True)
class AdamWStateTree:
    """One exact numerical tree; dense counts are scalar, table counts per row.

    uint64 scalar counts give whole-tensor participation. A uint64 vector whose
    length equals the parameter's leading extent gives per-row participation.
    The normative runtime/model_topology_v2.py parameter ledger, row admission
    and serialization must be bound by the complete-model and candidate
    transaction owners before this fixture tree becomes candidate state.
    """

    parameters: Mapping[str, mx.array]
    m: Mapping[str, mx.array]
    v: Mapping[str, mx.array]
    update_counts: Mapping[str, mx.array]
    schema_version: str = STATE_SCHEMA

    def __post_init__(self):
        self.validate()
        for name in ("parameters", "m", "v", "update_counts"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))

    def validate(self):
        """Inspect without rewriting the parent, including rejected/no-loss calls."""
        trees = (self.parameters, self.m, self.v, self.update_counts)
        if (self.schema_version != STATE_SCHEMA or any(not isinstance(tree, Mapping) for tree in trees) or
                not self.parameters or any(type(name) is not str or not name for name in self.parameters) or
                any(set(tree) != set(self.parameters) for tree in trees)):
            _invalid()
        for name, parameter in self.parameters.items():
            if (not isinstance(parameter, mx.array) or parameter.dtype != mx.float32 or
                    parameter.size < 1):
                _invalid()
            for moment in (self.m[name], self.v[name]):
                if not isinstance(moment, mx.array) or moment.shape != parameter.shape or moment.dtype != mx.float32:
                    _invalid()
            count = self.update_counts[name]
            if (not isinstance(count, mx.array) or count.dtype != mx.uint64 or
                    not (count.shape == () or (parameter.ndim >= ROW_COUNT_RANK and
                                              count.shape == (parameter.shape[0],)))):
                _invalid()
            if (not all(bool(mx.all(mx.isfinite(value))) for value in (parameter, self.m[name], self.v[name])) or
                    not bool(mx.all(self.v[name] >= 0))):
                _invalid()


def _preflight(parent, gradients, participation, hyperparameters, decay, loss_bearing):
    if (type(parent) is not AdamWStateTree or type(hyperparameters) is not AdamWHyperparameters or
            type(loss_bearing) is not bool or
            any(not isinstance(tree, Mapping) or set(tree) != set(parent.parameters)
                for tree in (gradients, participation, decay))):
        _invalid()
    parent.validate()
    hyperparameters.__post_init__()
    for name, parameter in parent.parameters.items():
        gradient, mask, count = gradients[name], participation[name], parent.update_counts[name]
        if (not isinstance(gradient, mx.array) or gradient.shape != parameter.shape or gradient.dtype != mx.float32 or
                not bool(mx.all(mx.isfinite(gradient))) or type(decay[name]) is not bool or
                not isinstance(mask, mx.array) or mask.dtype != mx.bool_ or mask.shape != count.shape):
            _invalid()
        if loss_bearing and bool(mx.any(mask & (count == mx.array(np.array(UINT64_MAX, dtype=np.uint64))))):
            _invalid()


def _adamw_update(parent: AdamWStateTree, gradients: Mapping[str, mx.array],
                  participation: Mapping[str, mx.array], hyperparameters: AdamWHyperparameters, *,
                  decay: Mapping[str, bool], loss_bearing: bool = True) -> AdamWStateTree:
    """Apply native AdamW only to selected numerical leaves/rows, without publication.

    Supplied gradients must already follow the caller's clipping contract.
    Masks are explicit Boolean scalars or row vectors, never inferred from
    nonzero gradients. Selected zero gradients still advance moments/counts.
    No-loss and wholly frozen steps return the original state object.
    """
    _preflight(parent, gradients, participation, hyperparameters, decay, loss_bearing)
    if not loss_bearing or not any(bool(mx.any(mask)) for mask in participation.values()):
        return parent
    parameters, first, second, counts = (dict(tree) for tree in
                                         (parent.parameters, parent.m, parent.v, parent.update_counts))
    for name, parameter in parent.parameters.items():
        mask = participation[name]
        if not bool(mx.any(mask)):
            continue
        count = parent.update_counts[name]
        rowwise = count.ndim == ROW_COUNT_RANK
        indices = mx.array(np.flatnonzero(np.asarray(mask)), dtype=mx.uint32) if rowwise else None
        selected = lambda value: value[indices] if rowwise else value
        next_count = selected(count) + 1
        step = next_count.reshape((-1,) + (1,) * (parameter.ndim-1)) if rowwise else next_count
        optimizer = optim.AdamW(learning_rate=hyperparameters.learning_rate, betas=hyperparameters.betas,
                                eps=hyperparameters.eps,
                                weight_decay=hyperparameters.weight_decay if decay[name] else 0,
                                bias_correction=True)
        optimizer.state = {"step": step, "learning_rate": mx.array(hyperparameters.learning_rate, dtype=mx.float32)}
        cell = {"m": selected(parent.m[name]), "v": selected(parent.v[name])}
        updated = optimizer.apply_single(selected(gradients[name]), selected(parameter), cell)
        for target, original, replacement in (
                (parameters, parameter, updated),
                (first, parent.m[name], cell["m"]),
                (second, parent.v[name], cell["v"])):
            if rowwise:
                candidate = mx.array(original)
                candidate[indices] = replacement
                target[name] = candidate
            else:
                target[name] = replacement
        counts[name] = count + mask.astype(mx.uint64) if rowwise else next_count
    return AdamWStateTree(parameters, first, second, counts)
