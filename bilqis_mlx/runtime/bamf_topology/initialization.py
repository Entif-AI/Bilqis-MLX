"""B01 initialization owner."""
from __future__ import annotations
import hashlib
import math
from typing import Mapping
from bilqis_mlx.errors import ErrorBus, SCHOOL
from .config import MATRIX_RANK, FEATURE_NONE_ROW, FEATURE_ROWS, FEATURE_DIM, GRAPH_FEATURE_DIM, SHA256_HEX_LENGTH, ModelTopologySpecV2
from .generation import GenerationExtents
from .parameters import Initializer, ParameterSpec


def initializer_seed(run_seed: int, parameter_path: str, row_id: str = "") -> int:
    """Derive an order-independent PCG64 seed from a stable path and row identity."""
    if (type(run_seed) is not int or not isinstance(parameter_path, str) or
            not parameter_path or not isinstance(row_id, str)):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    content = f"bamf.init.v2|{run_seed}|{parameter_path}|{row_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(content).digest()[:8], "little")


def initialize_bamf_parameter(parameter: ParameterSpec, *, run_seed: int):
    """Initialize one parameter. Identity and motif tables start unallocated."""
    import numpy as np

    if type(parameter) is not ParameterSpec:
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    seed = initializer_seed(run_seed, parameter.name)
    init = parameter.initializer
    if init in (Initializer.ZERO, Initializer.IDENTITY_BANK, Initializer.MOTIF_PAGE):
        return np.zeros(parameter.shape, dtype=np.float32)
    if init == Initializer.ONE:
        return np.ones(parameter.shape, dtype=np.float32)
    if init == Initializer.CONV_IDENTITY:
        value = np.zeros(parameter.shape, dtype=np.float32)
        value[:, 2] = 1.0
        return value
    if init in (Initializer.MINUS_TWO, Initializer.MINUS_FOUR, Initializer.LOG_ONE_NINTH):
        scalar = {Initializer.MINUS_TWO: -2.0, Initializer.MINUS_FOUR: -4.0,
                  Initializer.LOG_ONE_NINTH: math.log(1.0 / 9.0)}[init]
        return np.full(parameter.shape, scalar, dtype=np.float32)
    scale = 1.0 / math.sqrt(parameter.shape[-1]) if init == Initializer.MATRIX else 0.02
    value = (np.random.Generator(np.random.PCG64(seed)).standard_normal(parameter.shape) * scale).astype(np.float32)
    if init == Initializer.FEATURE_TABLE:
        value[FEATURE_NONE_ROW] = 0
    return value


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


def initialize_bamf_row(parameter: ParameterSpec, *, run_seed: int, row_id: str, factor=None):
    """Compute a row value; source admission and allocation remain upstream."""
    import numpy as np

    if (type(parameter) is not ParameterSpec or len(parameter.shape) != MATRIX_RANK or
            not isinstance(row_id, str) or not row_id):
        ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
    seed = initializer_seed(run_seed, parameter.name, row_id)
    noise = np.random.Generator(np.random.PCG64(seed)).standard_normal(parameter.shape[1])
    if parameter.initializer is Initializer.IDENTITY_BANK:
        try:
            factors = np.asarray(factor)
            valid = (factors.dtype == np.float32 and factors.shape == (parameter.shape[1],)
                     and bool(np.isfinite(factors).all()))
        except (TypeError, ValueError):
            valid = False
        if not valid:
            ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
        return (factors.astype(np.float64) + noise * 0.001).astype(np.float32)
    if parameter.initializer is Initializer.MOTIF_PAGE and factor is None:
        return (noise * 0.02).astype(np.float32)
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)
