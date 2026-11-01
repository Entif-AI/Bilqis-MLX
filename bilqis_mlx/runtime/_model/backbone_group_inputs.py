"""Validate fixed four-layer numerical group inputs without granting admission."""
from typing import Mapping
import mlx.core as mx
from bilqis_mlx.errors import ErrorBus, SCHOOL
from .model_topology_v2 import GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes


def _invalid():
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def validated_group_parameters(hidden, parameters, group_index, spec, extents,
                               scope_ids, valid, sequence_starts):
    if (type(spec) is not ModelTopologySpecV2
            or type(extents) is not GenerationExtents
            or type(group_index) is not int
            or not 1 <= group_index <= spec.depth_groups
            or type(hidden) is not mx.array
            or hidden.dtype != mx.float32 or hidden.ndim != 3
            or hidden.shape[-1] != spec.width
            or not 1 <= hidden.shape[1] <= spec.context
            or type(scope_ids) is not mx.array
            or scope_ids.dtype != mx.int32
            or scope_ids.shape != hidden.shape[:2]
            or type(valid) is not mx.array
            or valid.dtype != mx.bool_
            or valid.shape != hidden.shape[:2]
            or (sequence_starts is not None and (type(sequence_starts) is not mx.array
                or sequence_starts.dtype != mx.bool_
                or sequence_starts.shape != hidden.shape[:2]))
            or not isinstance(parameters, Mapping)
            or spec.layers % spec.depth_groups):
        _invalid()

    group_size = spec.layers // spec.depth_groups
    start = (group_index - 1) * group_size
    end = start + group_size
    required = {
        item.name: item.shape for item in expected_bamf_shapes(spec, extents)
        if item.name.startswith("blocks.")
        and start <= int(item.name.split(".")[1]) < end}
    for name, shape in required.items():
        value = parameters.get(name)
        if (type(value) is not mx.array or value.dtype != mx.float32
                or value.shape != shape):
            _invalid()
    return start, end, required
