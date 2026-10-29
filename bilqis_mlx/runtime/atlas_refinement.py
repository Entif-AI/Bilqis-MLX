"""Private B06 numerical recurrence pending source/backbone assembly.

This module does not publish refine_selected or authenticate hidden-state,
seed, member or role origins. B03/A05 and B05/B11 qualify those boundaries.
Prediction-local selection, quotas and routing supervision belong to B06.2.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from .model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes, validate_bamf_parameters,
)


WIDTH = ModelTopologySpecV2.width
INNER = 192
MEMBER_RANK = 2
MAX_LOCAL_PASSES = 2
RESIDUAL_GATE_SCALE = .1


def _invalid():
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


@dataclass(frozen=True)
class _RefinementResult:
    hidden: mx.array
    route_logits: mx.array | None
    passes: int
    schema_version: str = "bilqis.mlx.refinement-numerical-result/provisional-v1"


def refinement_parameter_view(parameters: Mapping[str, mx.array], *, spec: ModelTopologySpecV2,
                              extents: GenerationExtents) -> dict[str, mx.array]:
    """Borrow exact refinement tensors after validating the full B01 tree."""
    validate_bamf_parameters(spec, extents, parameters)
    return {item.name: parameters[item.name] for item in expected_bamf_shapes(spec, extents)
            if item.name.startswith("refine.")}


def _norm(value, gamma):
    return mx.fast.rms_norm(value, gamma, ModelTopologySpecV2.rms_norm_epsilon)


def _validate(hidden, seed, members, role, passes, parameters):
    if (type(passes) is not int or not 0 <= passes <= MAX_LOCAL_PASSES or
            not isinstance(parameters, Mapping)):
        _invalid()
    for value in (hidden, seed, role):
        if not isinstance(value, mx.array) or value.shape != (WIDTH,) or value.dtype != mx.float32:
            _invalid()
    if (not isinstance(members, mx.array) or members.ndim != MEMBER_RANK or
            members.shape[0] < 1 or members.shape[1] != WIDTH or members.dtype != mx.float32):
        _invalid()
    # Shapes are independent of generation extents; the canonical ledger owns them.
    extents = GenerationExtents(1, 1, "0"*64, "0"*64, "0"*64)
    declarations = tuple(item for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)
                         if item.name.startswith("refine."))
    if set(parameters) != {item.name for item in declarations}:
        _invalid()
    for item in declarations:
        value = parameters[item.name]
        if not isinstance(value, mx.array) or value.shape != item.shape or value.dtype != mx.float32:
            _invalid()
    if not all(bool(mx.all(mx.isfinite(value))) for value in
               (hidden, seed, members, role, *parameters.values())):
        _invalid()


def _refine_frame(hidden: mx.array, seed: mx.array, members: mx.array, role: mx.array,
                  passes: int, parameters: Mapping[str, mx.array]) -> _RefinementResult:
    """Run a supplied complete, unmasked fixture frame for zero, one or two passes.

    All vectors are FP32. Hidden/seed/role are768-wide, members are[M,768].
    Inputs remain unchanged; every pass recalls the same original seed and
    members. No backbone, source lookup, routing decision or state write occurs.
    """
    _validate(hidden, seed, members, role, passes, parameters)
    if passes == 0:
        return _RefinementResult(hidden, None, 0)
    keys = members @ parameters["refine.key"].T
    values = members @ parameters["refine.value"].T
    state = hidden
    for _ in range(passes):
        query = _norm(state + seed + role, parameters["refine.norm"]) @ parameters["refine.query"].T
        attention = mx.softmax((query @ keys.T) / INNER**.5, axis=-1)
        residual = (attention @ values) @ parameters["refine.output"].T
        gate = RESIDUAL_GATE_SCALE * mx.sigmoid(
            mx.sum(_norm(state, parameters["refine.norm"]) * parameters["refine.gate_vector"]) +
            parameters["refine.bias"])
        state = state + gate * residual
    route_logits = state @ parameters["refine.route"].T + parameters["refine.route_bias"]
    if not bool(mx.all(mx.isfinite(state))) or not bool(mx.all(mx.isfinite(route_logits))):
        _invalid()
    return _RefinementResult(state, route_logits, passes)
