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
ROUTE_LOGIT_DIM = MAX_LOCAL_PASSES + 1
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


def _validate_refinement_parameters(parameters):
    if not isinstance(parameters, Mapping):
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
    if not all(bool(mx.all(mx.isfinite(value))) for value in parameters.values()):
        _invalid()


def _validate(hidden, seed, members, role, passes, parameters):
    if type(passes) is not int or not 0 <= passes <= MAX_LOCAL_PASSES:
        _invalid()
    for value in (hidden, seed, role):
        if not isinstance(value, mx.array) or value.shape != (WIDTH,) or value.dtype != mx.float32:
            _invalid()
    if (not isinstance(members, mx.array) or members.ndim != MEMBER_RANK or
            members.shape[0] < 1 or members.shape[1] != WIDTH or members.dtype != mx.float32):
        _invalid()
    _validate_refinement_parameters(parameters)
    if not all(bool(mx.all(mx.isfinite(value))) for value in
               (hidden, seed, members, role)):
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


def routing_logits_from_state(hidden: mx.array, parameters: Mapping[str, mx.array]) -> mx.array:
    """Train the 0/1/2 route head before any local refinement pass.

    The zero-pass numerical kernel retains its exact hidden-object identity
    and does not run a route head. This separate prediction-local readout
    supplies class-0 supervision without fabricating a refinement pass.
    """
    if (not isinstance(hidden, mx.array) or hidden.shape != (WIDTH,)
            or hidden.dtype != mx.float32
            or not bool(mx.all(mx.isfinite(hidden)))):
        _invalid()
    _validate_refinement_parameters(parameters)
    logits = hidden @ parameters["refine.route"].T + parameters["refine.route_bias"]
    if not bool(mx.all(mx.isfinite(logits))):
        _invalid()
    return logits


def masked_routing_loss(route_logits: mx.array | None, route_label: int | None) -> mx.array:
    """Missing route supervision contributes zero, not a fabricated target.

    This auxiliary term never replaces the answer loss, which still backprops
    through the selected numerical refinement path.
    """
    if route_logits is None:
        if route_label is not None:
            _invalid()
        return mx.array(0.0, dtype=mx.float32)
    if (not isinstance(route_logits, mx.array)
            or route_logits.shape != (ROUTE_LOGIT_DIM,)
            or route_logits.dtype != mx.float32
            or not bool(mx.all(mx.isfinite(route_logits)))
            or (route_label is not None
                and (type(route_label) is not int or not 0 <= route_label <= MAX_LOCAL_PASSES))):
        _invalid()
    if route_label is None:
        return mx.sum(route_logits * 0.0)
    return mx.logsumexp(route_logits) - route_logits[route_label]
