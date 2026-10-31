"""B01 state owner."""
from __future__ import annotations
from typing import Mapping
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.model_topology import DEFAULT_OPTIMIZER
from .config import IDENTITY_ESTABLISHED_AGE, ModelTopologySpecV2
from .generation import GenerationExtents
from .parameters import ParameterGroup
from .ledger import expected_bamf_shapes, bamf_parameter_census
from .initialization import initializer_seed, initialize_bamf_parameter


def validate_bamf_parameters(spec: ModelTopologySpecV2, extents: GenerationExtents,
                             parameters: Mapping[str, object]) -> None:
    """Check exact names, shapes and FP32 arrays against the declared ledger."""
    import mlx.core as mx

    declared = expected_bamf_shapes(spec, extents)
    if not isinstance(parameters, Mapping) or set(parameters) != {item.name for item in declared}:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID)
    for item in declared:
        value = parameters[item.name]
        if not isinstance(value, mx.array) or value.dtype != mx.float32 or tuple(value.shape) != item.shape:
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID, parameter=item.name)


def create_unbound_bamf_state(spec: ModelTopologySpecV2, extents: GenerationExtents,
                              *, run_seed: int):
    """Construct disposable unbound tensors and zero moments, without admitting rows.

    Source-bound identity and allocated motif rows require their respective
    owners. This state is not a releasable model or a trainable optimizer.
    """
    import mlx.core as mx

    census = bamf_parameter_census(spec, extents)
    declared = census.parameters
    initializer_seed(run_seed, "validation")
    parameters = {item.name: mx.array(initialize_bamf_parameter(item, run_seed=run_seed), dtype=mx.float32)
                  for item in declared}
    state = {
        "step": mx.array(0, dtype=mx.uint64),
        "learning_rate": mx.array(DEFAULT_OPTIMIZER["learning_rate"], dtype=mx.float32),
        **{item.name: {"m": mx.zeros(item.shape, dtype=mx.float32),
                       "v": mx.zeros(item.shape, dtype=mx.float32)} for item in declared},
    }
    mx.eval(parameters, state)
    validate_bamf_parameters(spec, extents, parameters)
    manifest = {
        "schema": "bilqis.mlx.bamf-initialization/v1",
        "initialization_status": "UNBOUND",
        "topology_digest": spec.digest,
        "shape_policy_digest": spec.shape_policy_digest,
        "generation_extents_digest": extents.digest,
        "generation_extents": extents.to_record(),
        "run_seed": run_seed,
        "parameter_count": census.total,
        "parameter_subtotals": {kind.value: count for kind, count in census.subtotals.items()},
        "identity_row_group_policy": {
            "before_age": ParameterGroup.FAST.value,
            "from_age": ParameterGroup.SLOW.value,
            "established_at": IDENTITY_ESTABLISHED_AGE,
            "age_unit": "accepted-participating-candidates",
        },
        "optimizer": {"algorithm": "AdamW", "learning_rate": DEFAULT_OPTIMIZER["learning_rate"],
                      "betas": list(DEFAULT_OPTIMIZER["betas"]), "eps": DEFAULT_OPTIMIZER["eps"],
                      "weight_decay": DEFAULT_OPTIMIZER["weight_decay"], "bias_correction": True},
        "parameters": [{"name": item.name, "shape": list(item.shape), "dtype": item.dtype,
                        "parameters": item.parameter_count, "category": item.category.value,
                        "initializer": item.initializer.value, "group": item.group.value,
                        "decay": item.decay,
                        "storage_keys": {part: bamf_storage_key(item.name, part)
                                         for part in ("weight", "m", "v")}}
                       for item in declared],
        "serialization_schema": "bilqis.mlx.bamf-named-tensors/v1",
        "constants": ["sinusoidal_positions", "sha256_literal_features", "visibility_masks"],
    }
    return parameters, state, manifest


def bamf_storage_key(parameter_name: str, part: str) -> str:
    """Encode the stable parameter path without relying on registry position."""
    if not isinstance(parameter_name, str) or not parameter_name or part not in ("weight", "m", "v"):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    try:
        encoded = parameter_name.encode("utf-8").hex()
    except UnicodeEncodeError:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    return f"p{encoded}_{part}"


def bamf_serialization_arrays(spec: ModelTopologySpecV2, extents: GenerationExtents,
                              parameters: Mapping[str, object], state: Mapping[str, object]) -> dict:
    """Produce stable path-derived serialization keys after validating the tree."""
    import mlx.core as mx

    declared = expected_bamf_shapes(spec, extents)
    validate_bamf_parameters(spec, extents, parameters)
    if not isinstance(state, Mapping) or set(state) != {"step", "learning_rate", *(x.name for x in declared)}:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID)
    step, learning_rate = state["step"], state["learning_rate"]
    if (not isinstance(step, mx.array) or step.dtype != mx.uint64 or tuple(step.shape) != () or
            not isinstance(learning_rate, mx.array) or learning_rate.dtype != mx.float32 or
            tuple(learning_rate.shape) != ()):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID)
    arrays = {}
    for item in declared:
        moments = state[item.name]
        if not isinstance(moments, Mapping) or set(moments) != {"m", "v"}:
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID, parameter=item.name)
        for part, value in (("weight", parameters[item.name]), ("m", moments["m"]), ("v", moments["v"])):
            if not isinstance(value, mx.array) or value.dtype != mx.float32 or tuple(value.shape) != item.shape:
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID, parameter=item.name)
            arrays[bamf_storage_key(item.name, part)] = value
    arrays["adamw_global_step"] = step
    arrays["adamw_learning_rate"] = learning_rate
    return arrays


def bamf_deserialize_arrays(spec: ModelTopologySpecV2, extents: GenerationExtents,
                            arrays: Mapping[str, object]) -> tuple[dict, dict]:
    """Reconstruct an unbound tree only from its complete declared array set."""
    declared = expected_bamf_shapes(spec, extents)
    expected = {bamf_storage_key(item.name, part)
                for item in declared for part in ("weight", "m", "v")}
    expected.update(("adamw_global_step", "adamw_learning_rate"))
    if not isinstance(arrays, Mapping) or set(arrays) != expected:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.PARAMETER_SHAPES_INVALID)
    parameters = {item.name: arrays[bamf_storage_key(item.name, "weight")] for item in declared}
    state = {"step": arrays["adamw_global_step"], "learning_rate": arrays["adamw_learning_rate"],
             **{item.name: {"m": arrays[bamf_storage_key(item.name, "m")],
                            "v": arrays[bamf_storage_key(item.name, "v")]} for item in declared}}
    bamf_serialization_arrays(spec, extents, parameters, state)
    return parameters, state
