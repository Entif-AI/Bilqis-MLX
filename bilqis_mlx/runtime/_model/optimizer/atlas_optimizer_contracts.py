"""Structural and state contracts for the BAMF AdamW numerical owner."""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.optimizer_count_geometry import declared_update_count_shape

DENSE_COUNT_RANK = 0
ROW_COUNT_RANK = 1
ROW_SELECTION_PARTS = 2
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

    def validate_structure(self):
        """Validate CPU-visible schema, tree, shape and dtype invariants only."""
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

    def validate(self):
        """Validate structure plus one aggregated device-visible numerical predicate."""
        self.validate_structure()
        checks = _state_numerical_checks(self)
        valid = mx.all(mx.stack(tuple(checks)))
        mx.eval(valid)
        if not bool(valid):
            _invalid()


def _issue_learning_first_state(parameters, first, second, counts):
    """Issue ordinary-training state without a second full numerical proof sweep."""
    state = object.__new__(AdamWStateTree)
    for name, value in (
        ("parameters", parameters), ("m", first), ("v", second),
        ("update_counts", counts), ("schema_version", STATE_SCHEMA),
    ):
        object.__setattr__(state, name, value)
    state.validate_structure()
    for name in ("parameters", "m", "v", "update_counts"):
        object.__setattr__(state, name, MappingProxyType(dict(getattr(state, name))))
    return state


def _state_numerical_checks(state: AdamWStateTree):
    """Return lazy device predicates for one structurally validated optimizer state."""
    checks = []
    for name, parameter in state.parameters.items():
        checks.extend((
            mx.all(mx.isfinite(parameter)),
            mx.all(mx.isfinite(state.m[name])),
            mx.all(mx.isfinite(state.v[name])),
            mx.all(state.v[name] >= 0),
        ))
    return checks


def reconcile_b01_optimizer_manifest(
        state: AdamWStateTree, spec, extents) -> Mapping[str, bool]:
    """Validate one optimizer tree against B01 and return its decay manifest.

    B01 owns the complete parameter names, shapes, initializers and decay flags.
    B12 adds moments/counts but cannot invent a parallel tree or caller-authored
    decay policy. Order is checked as well as membership so serialization and
    optimizer custody consume the same expanded ParameterSpec sequence.
    """
    from bilqis_mlx.runtime.model_topology_v2 import (
        GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
        validate_bamf_parameters,
    )

    if (type(state) is not AdamWStateTree
            or type(spec) is not ModelTopologySpecV2
            or type(extents) is not GenerationExtents):
        _invalid()
    state.validate_structure()
    validate_bamf_parameters(spec, extents, state.parameters)
    declared = expected_bamf_shapes(spec, extents)
    names = tuple(item.name for item in declared)
    if any(tuple(tree) != names for tree in (
            state.parameters, state.m, state.v, state.update_counts)):
        _invalid()
    for item in declared:
        if (state.parameters[item.name].shape != item.shape
                or state.m[item.name].shape != item.shape
                or state.v[item.name].shape != item.shape
                or state.update_counts[item.name].shape
                != declared_update_count_shape(item)):
            _invalid()
    return MappingProxyType({item.name: item.decay for item in declared})
