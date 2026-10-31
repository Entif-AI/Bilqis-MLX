"""B01 validation ownership; historical tensor and initializer contracts retained."""
from __future__ import annotations
from bilqis_mlx.errors import ErrorBus
from bilqis_mlx.errors import SCHOOL
from typing import Mapping
from .spec import ModelTopologySpecV2
from .records import GenerationExtents
from .ledger import expected_bamf_shapes


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
