"""Disposable exact-value prefix reuse witness; not a BAMF runtime cache."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib

import mlx.core as mx
import numpy as np


def tensor_digest(value) -> str:
    array = np.asarray(value)
    digest = hashlib.sha256()
    digest.update(str((array.shape, array.dtype)).encode())
    digest.update(array.tobytes())
    return digest.hexdigest()


@dataclass(frozen=True)
class RegionScope:
    admission: str
    candidate_epoch: str
    input_contract: str


class FrozenRegion:
    """One numerical prefix: reuse only with entirely frozen dependencies.

    Call outside autodiff. A miss due to trainable support returns None, so
    callers must execute the original differentiable path, not detach it.
    Keys deliberately use exact tensor bytes for this bounded proof; hashing
    full production tensors per step is not proposed as an optimization.
    """

    def __init__(self):
        self._entry = None
        self.hits = 0
        self.misses = 0
        self.bypasses = 0

    def invalidate(self):
        self._entry = None

    def get(self, scope, inputs, prefix_parameters, trainable, compute):
        if set(prefix_parameters).intersection(trainable):
            self.invalidate()
            self.bypasses += 1
            return None
        key = (scope, tensor_digest(inputs), tuple(
            (name, tensor_digest(value))
            for name, value in sorted(prefix_parameters.items())))
        if self._entry is not None and self._entry[0] == key:
            self.hits += 1
            return self._entry[1]
        value = mx.stop_gradient(compute(inputs, prefix_parameters))
        mx.eval(value)
        self._entry = (key, value)
        self.misses += 1
        return value
