"""B01 factors ownership; historical tensor and initializer contracts retained."""
from __future__ import annotations
from bilqis_mlx.errors import ErrorBus
from bilqis_mlx.errors import SCHOOL
from typing import Mapping
from .spec import ModelTopologySpecV2
from .dimensions import FEATURE_DIM, FEATURE_NONE_ROW, FEATURE_ROWS, GRAPH_FEATURE_DIM, SHA256_HEX_LENGTH
from .records import GenerationExtents


def project_identity_source_factor(
    parameters: Mapping[str, object], *,
    type_rows: tuple[int, ...],
    type_overflow: tuple[tuple[float, ...] | None, ...],
    graph64: tuple[float, ...],
    extents: GenerationExtents,
    predecessor_feature_digest: str,
):
    """Project source-attested prospective identity features without B02 authority.

    A02 uses this read-only staging primitive before identity-row activation. The
    caller must bind the source feature plan to the accepted predecessor feature
    digest. Role/schema/local context deliberately stays outside identity seeding.
    """
    import mlx.core as mx
    import numpy as np

    if (not isinstance(parameters, Mapping)
            or not isinstance(extents, GenerationExtents)
            or not isinstance(predecessor_feature_digest, str)
            or len(predecessor_feature_digest) != SHA256_HEX_LENGTH
            or any(character not in "0123456789abcdef"
                   for character in predecessor_feature_digest)
            or extents.factor_map_digest != predecessor_feature_digest):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    expected = {
        "features.type": (FEATURE_ROWS, FEATURE_DIM),
        "features.project_type": (ModelTopologySpecV2.width, FEATURE_DIM),
        "features.project_graph": (ModelTopologySpecV2.width, GRAPH_FEATURE_DIM),
        "features.gates": (4,),
    }
    for name, shape in expected.items():
        value = parameters.get(name)
        if (not isinstance(value, mx.array) or value.dtype != mx.float32
                or value.shape != shape):
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    if (not isinstance(type_rows, tuple) or not isinstance(type_overflow, tuple)
            or len(type_rows) != len(type_overflow)
            or not isinstance(graph64, tuple) or len(graph64) != GRAPH_FEATURE_DIM
            or any(type(row) is not int or not 0 <= row < FEATURE_ROWS for row in type_rows)):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    try:
        graph = np.asarray(graph64, dtype=np.float32)
    except (TypeError, ValueError, OverflowError):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    if graph.shape != (GRAPH_FEATURE_DIM,) or not np.isfinite(graph).all():
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)

    type_vectors = []
    for row, overflow in zip(type_rows, type_overflow):
        value = parameters["features.type"][row]
        if overflow is not None:
            try:
                overflow_array = np.asarray(overflow, dtype=np.float32)
            except (TypeError, ValueError, OverflowError):
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
            if (row != 0 or overflow_array.shape != (FEATURE_DIM,)
                    or not np.isfinite(overflow_array).all()):
                ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
            value = value + mx.array(overflow_array, dtype=mx.float32)
        type_vectors.append(value)
    type_mean = (mx.mean(mx.stack(type_vectors), axis=0) if type_vectors
                 else parameters["features.type"][FEATURE_NONE_ROW])
    gates = mx.sigmoid(parameters["features.gates"])
    factor = (
        gates[0] * (type_mean @ parameters["features.project_type"].T)
        + gates[3] * (mx.array(graph, dtype=mx.float32)
                      @ parameters["features.project_graph"].T)
    )
    mx.eval(factor)
    result = np.asarray(factor, dtype=np.float32)
    if result.shape != (ModelTopologySpecV2.width,) or not np.isfinite(result).all():
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    return result
