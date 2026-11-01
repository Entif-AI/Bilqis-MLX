"""B01 serialization ownership; historical tensor and initializer contracts retained."""
from __future__ import annotations
from bilqis_mlx.errors import ErrorBus
from bilqis_mlx.errors import SCHOOL
from typing import Mapping
from .spec import ModelTopologySpecV2
from .records import GenerationExtents
from .ledger import expected_bamf_shapes
from .validation import validate_bamf_parameters


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
