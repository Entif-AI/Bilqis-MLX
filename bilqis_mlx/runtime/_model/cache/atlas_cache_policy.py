"""Inference-only policy for compatible BAMF derived-cache responses."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

import numpy as np

from bilqis_mlx.errors import BilqisError

from .atlas_cache_binding import (
    CacheArtifact,
    CacheBinding,
    CacheByteCost,
    cache_byte_cost,
    require_cache_binding,
)


FALLBACK_BINDING = "BINDING_MISMATCH"
FALLBACK_DECODE = "DECODE_INVALID"
FALLBACK_TYPED_ANSWER = "TYPED_ANSWER_INVALID"
FALLBACK_SCORE_DRIFT = "SCORE_DRIFT_EXCEEDED"
REFERENCE_DIMS_MIN = 1


@dataclass(frozen=True)
class CacheQualityPolicy:
    max_score_drift: float

    def validate(self) -> None:
        if (
            type(self.max_score_drift) is not float
            or not math.isfinite(self.max_score_drift)
            or self.max_score_drift < 0.0
        ):
            _invalid()


@dataclass(frozen=True)
class CacheQualityObservation:
    typed_answer_valid: bool
    score_drift: float

    def validate(self) -> None:
        if (
            type(self.typed_answer_valid) is not bool
            or type(self.score_drift) is not float
            or not math.isfinite(self.score_drift)
            or self.score_drift < 0.0
        ):
            _invalid()


@dataclass(frozen=True)
class CacheInferenceResult:
    value: object
    used_cache: bool
    fallback_reason: str | None
    byte_cost: CacheByteCost | None


def _invalid() -> None:
    from .atlas_cache_codec import _invalid as codec_invalid
    codec_invalid()


def reference_candidate_evaluation(
    fp32_state, evaluator: Callable[[np.ndarray], object],
) -> object:
    """Evaluate reference candidates only from finite authoritative FP32 state."""
    values = np.asarray(fp32_state)
    if (
        values.ndim < REFERENCE_DIMS_MIN
        or values.dtype != np.dtype(np.float32)
        or not np.isfinite(values).all()
        or not callable(evaluator)
    ):
        _invalid()
    return evaluator(np.array(values, dtype=np.float32, copy=True, order="C"))


def _fallback(fp32_recompute, reason: str) -> CacheInferenceResult:
    if not callable(fp32_recompute):
        _invalid()
    return CacheInferenceResult(fp32_recompute(), False, reason, None)


def interactive_cache_inference(
    artifact: CacheArtifact,
    expected_binding: CacheBinding,
    *,
    cached_infer: Callable[[np.ndarray], object],
    fp32_recompute: Callable[[], object],
    quality_check: Callable[[object], CacheQualityObservation],
    policy: CacheQualityPolicy,
) -> CacheInferenceResult:
    """Use a derived cache only after binding, decode, and declared quality checks."""
    if not isinstance(policy, CacheQualityPolicy):
        _invalid()
    policy.validate()
    try:
        require_cache_binding(artifact, expected_binding)
    except BilqisError:
        return _fallback(fp32_recompute, FALLBACK_BINDING)
    from .atlas_cache_records import decode_cache
    try:
        approximate = decode_cache(artifact, expected_binding)
    except BilqisError:
        return _fallback(fp32_recompute, FALLBACK_DECODE)
    if not callable(cached_infer) or not callable(quality_check):
        _invalid()
    candidate = cached_infer(approximate)
    observation = quality_check(candidate)
    if not isinstance(observation, CacheQualityObservation):
        _invalid()
    observation.validate()
    if not observation.typed_answer_valid:
        return _fallback(fp32_recompute, FALLBACK_TYPED_ANSWER)
    if observation.score_drift > policy.max_score_drift:
        return _fallback(fp32_recompute, FALLBACK_SCORE_DRIFT)
    return CacheInferenceResult(
        candidate, True, None, cache_byte_cost(artifact)
    )
