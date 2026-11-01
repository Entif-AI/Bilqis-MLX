"""B01 initialization ownership; historical tensor and initializer contracts retained."""
from __future__ import annotations
from bilqis_mlx.errors import ErrorBus
from bilqis_mlx.errors import SCHOOL
import math
from .spec import initializer_seed
from .dimensions import FEATURE_NONE_ROW, MATRIX_RANK
from .records import Initializer, ParameterSpec


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
