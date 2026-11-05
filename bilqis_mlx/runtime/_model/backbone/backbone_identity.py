"""Content identity for the complete declared BAMF parameter tree."""
from __future__ import annotations

import hashlib
import json
from typing import Mapping

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import ErrorBus, SCHOOL
from .model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
    validate_bamf_parameters,
)


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def tensor_content_digest(value: mx.array) -> str:
    if type(value) is not mx.array:
        _invalid()
    return hashlib.sha256(np.asarray(mx.stop_gradient(value)).tobytes()).hexdigest()


def bamf_parameter_tree_digest(
    parameters: Mapping[str, mx.array], *, spec: ModelTopologySpecV2,
    extents: GenerationExtents,
) -> str:
    """Hash every declared BAMF tensor by name, shape, dtype and content."""
    if (type(spec) is not ModelTopologySpecV2
            or type(extents) is not GenerationExtents
            or not isinstance(parameters, Mapping)):
        _invalid()
    validate_bamf_parameters(spec, extents, parameters)
    names = tuple(item.name for item in expected_bamf_shapes(spec, extents))
    record = [
        (name, tuple(parameters[name].shape), str(parameters[name].dtype),
         tensor_content_digest(parameters[name]))
        for name in names
    ]
    return hashlib.sha256(json.dumps(
        record, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def execution_generation_digest(
    parameters: Mapping[str, mx.array], *, spec: ModelTopologySpecV2,
    extents: GenerationExtents,
) -> str:
    """Content identity of the current executable model, not retained custody."""
    tree = bamf_parameter_tree_digest(parameters, spec=spec, extents=extents)
    return hashlib.sha256(json.dumps((
        "bilqis.mlx.execution-generation/v2", spec.digest, extents.digest, tree,
    ), separators=(",", ":")).encode()).hexdigest()
