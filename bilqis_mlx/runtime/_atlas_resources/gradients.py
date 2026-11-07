"""C08.1 gradient accumulation and single-step backend receipt contract."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

from .contracts import (
    ACCUMULATED_GRADIENT_SCHEMA, BACKEND_STEP_SCHEMA,
    GRADIENT_CHUNK_SCHEMA, BatchPlan, _digest, _finite, _invalid, _sha,
)

@dataclass(frozen=True)
class GradientChunk:
    row_indices: tuple[int, ...]
    mean_gradient: tuple[float, ...]
    mean_loss: float
    optimizer_step_seed: int
    generation_binding: str
    schema_version: str = GRADIENT_CHUNK_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.row_indices, tuple)
                or not self.row_indices
                or any(type(index) is not int or index < 0
                       for index in self.row_indices)
                or not isinstance(self.mean_gradient, tuple)
                or not self.mean_gradient
                or any(not _finite(value) for value in self.mean_gradient)
                or not _finite(self.mean_loss)
                or type(self.optimizer_step_seed) is not int
                or self.optimizer_step_seed < 0
                or not isinstance(self.generation_binding, str)
                or not self.generation_binding
                or self.schema_version != GRADIENT_CHUNK_SCHEMA):
            _invalid("BAMF_C08_GRADIENT_CHUNK_INVALID")


@dataclass(frozen=True)
class AccumulatedGradient:
    gradient: tuple[float, ...]
    global_norm: float
    clip_scale: float
    weighted_mean_loss: float
    logical_rows: int
    generation_binding: str
    source_digest: str
    gradient_digest: str
    schema_version: str = ACCUMULATED_GRADIENT_SCHEMA

    def __post_init__(self) -> None:
        if (not self.gradient
                or any(not _finite(value) for value in self.gradient)
                or any(not _finite(value) for value in (
                    self.global_norm, self.clip_scale,
                    self.weighted_mean_loss))
                or not 0 < self.clip_scale <= 1
                or type(self.logical_rows) is not int
                or self.logical_rows < 1
                or not isinstance(self.generation_binding, str)
                or not self.generation_binding
                or not _sha(self.source_digest)
                or not _sha(self.gradient_digest)
                or self.gradient_digest != _digest(self.gradient)
                or self.schema_version != ACCUMULATED_GRADIENT_SCHEMA):
            _invalid("BAMF_C08_ACCUMULATED_GRADIENT_INVALID")


def accumulate_gradients(
    plan: BatchPlan,
    chunks: tuple[GradientChunk, ...],
    *,
    clip_norm: float,
) -> AccumulatedGradient:
    if (not isinstance(plan, BatchPlan)
            or not isinstance(chunks, tuple)
            or len(chunks) != len(plan.groups)
            or any(not isinstance(chunk, GradientChunk)
                   for chunk in chunks)
            or not _finite(clip_norm) or clip_norm <= 0):
        _invalid("BAMF_C08_GRADIENT_ARGUMENT_INVALID")
    if any(
        chunk.row_indices != group
        or chunk.optimizer_step_seed != plan.optimizer_step_seed
        or chunk.generation_binding != plan.generation_binding
        for chunk, group in zip(chunks, plan.groups)
    ):
        _invalid("BAMF_C08_GRADIENT_SOURCE_DRIFT")
    dimensions = {len(chunk.mean_gradient) for chunk in chunks}
    if len(dimensions) != 1:
        _invalid("BAMF_C08_GRADIENT_DIMENSION_DRIFT")
    total = len(plan.logical_row_ids)
    gradient = tuple(
        math.fsum(
            len(chunk.row_indices) * chunk.mean_gradient[dimension]
            for chunk in chunks
        ) / total
        for dimension in range(next(iter(dimensions)))
    )
    norm = math.sqrt(math.fsum(value * value for value in gradient))
    scale = min(1.0, clip_norm / norm) if norm else 1.0
    clipped = tuple(value * scale for value in gradient)
    mean_loss = math.fsum(
        len(chunk.row_indices) * chunk.mean_loss for chunk in chunks
    ) / total
    return AccumulatedGradient(
        gradient=clipped,
        global_norm=norm,
        clip_scale=scale,
        weighted_mean_loss=mean_loss,
        logical_rows=total,
        generation_binding=plan.generation_binding,
        source_digest=plan.source_digest,
        gradient_digest=_digest(clipped),
    )


@dataclass(frozen=True)
class BackendStepReceipt:
    optimizer_steps_applied: int
    generation_binding: str
    source_digest: str
    gradient_digest: str
    new_state_digest: str
    schema_version: str = BACKEND_STEP_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.optimizer_steps_applied) is not int
                or self.optimizer_steps_applied != 1
                or not isinstance(self.generation_binding, str)
                or not self.generation_binding
                or not all(_sha(item) for item in (
                    self.source_digest, self.gradient_digest,
                    self.new_state_digest))
                or self.schema_version != BACKEND_STEP_SCHEMA):
            _invalid("BAMF_C08_BACKEND_STEP_RECEIPT_INVALID")


def apply_one_adamw_step(
    accumulated: AccumulatedGradient,
    backend_apply: Callable[[tuple[float, ...], str, str], BackendStepReceipt],
) -> BackendStepReceipt:
    """Invoke B11's sole optimizer owner exactly once; verify its receipt."""
    if not isinstance(accumulated, AccumulatedGradient) or not callable(backend_apply):
        _invalid("BAMF_C08_BACKEND_ARGUMENT_INVALID")
    receipt = backend_apply(
        accumulated.gradient,
        accumulated.generation_binding,
        accumulated.source_digest)
    if (not isinstance(receipt, BackendStepReceipt)
            or receipt.generation_binding != accumulated.generation_binding
            or receipt.source_digest != accumulated.source_digest
            or receipt.gradient_digest != accumulated.gradient_digest):
        _invalid("BAMF_C08_BACKEND_STEP_DRIFT")
    return receipt
