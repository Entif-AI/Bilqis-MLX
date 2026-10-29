"""C08.1 pure topology-aware memory and one-step gradient plan.

This owner consumes measured compiler frame statistics and B01's parameter
census. It does not allocate MLX arrays or acquire optimizer write authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
from typing import Callable

from ..errors import ErrorBus, SCHOOL
from .model_topology_v2 import ModelTopologySpecV2, ParameterCensus


FRAME_STATS_SCHEMA = "bilqis.c08.frame-stats/v1"
RESOURCE_ROW_SCHEMA = "bilqis.c08.resource-row/v1"
MEMORY_BUDGET_SCHEMA = "bilqis.c08.memory-budget/v1"
BATCH_PLAN_SCHEMA = "bilqis.c08.batch-plan/v1"
GRADIENT_CHUNK_SCHEMA = "bilqis.c08.gradient-chunk/v1"
ACCUMULATED_GRADIENT_SCHEMA = "bilqis.c08.accumulated-gradient/v1"
BACKEND_STEP_SCHEMA = "bilqis.c08.backend-step-receipt/v1"
TRAINER_ALLOCATION_BYTES = 48 * 1024**3
DEFAULT_POSITION_BUDGET = 4096
MICROBATCH_SIZES = (32, 16, 8, 4, 2, 1)
FP32_BYTES = 4
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_RESOURCES.INVALID, reason=reason)


def _digest(value: object) -> str:
    return hashlib.sha256(
        (json.dumps(value, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    ).hexdigest()


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True)
class FrameStats:
    compiled_positions: int
    frame_lengths: tuple[int, ...]
    constituent_expansions: int
    depth_summaries: int
    schema_version: str = FRAME_STATS_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.compiled_positions) is not int
                or self.compiled_positions < 1
                or not isinstance(self.frame_lengths, tuple)
                or not self.frame_lengths
                or any(type(item) is not int or item < 1
                       for item in self.frame_lengths)
                or type(self.constituent_expansions) is not int
                or self.constituent_expansions < 0
                or type(self.depth_summaries) is not int
                or self.depth_summaries < 0
                or self.schema_version != FRAME_STATS_SCHEMA):
            _invalid("BAMF_C08_FRAME_STATS_INVALID")


@dataclass(frozen=True)
class ResourceRow:
    row_id: str
    frame_stats: FrameStats
    target_decisions: int
    optimizer_step_seed: int
    generation_binding: str
    schema_version: str = RESOURCE_ROW_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.row_id, str) or not self.row_id
                or not isinstance(self.frame_stats, FrameStats)
                or type(self.target_decisions) is not int
                or self.target_decisions < 1
                or type(self.optimizer_step_seed) is not int
                or self.optimizer_step_seed < 0
                or not isinstance(self.generation_binding, str)
                or not self.generation_binding
                or self.schema_version != RESOURCE_ROW_SCHEMA):
            _invalid("BAMF_C08_RESOURCE_ROW_INVALID")

    @classmethod
    def from_training_row(
        cls, training_row: object, frame_stats: FrameStats,
        *, generation_binding: str,
    ) -> "ResourceRow":
        """Bind exact C02 delivery identity to A05-owned compiler statistics."""
        from .atlas_training_adapter import BamfTrainingRow

        if (not isinstance(training_row, BamfTrainingRow)
                or not isinstance(frame_stats, FrameStats)
                or not isinstance(training_row.model_input.answer_plan, tuple)):
            _invalid("BAMF_C08_DELIVERY_PROFILE_INVALID")
        plan = dict(training_row.model_input.answer_plan)
        if (plan.get("generation_binding") != generation_binding
                or type(plan.get("maximum_decisions")) is not int):
            _invalid("BAMF_C08_DELIVERY_PROFILE_INVALID")
        return cls(
            row_id=training_row.provenance.row_id,
            frame_stats=frame_stats,
            target_decisions=plan["maximum_decisions"],
            optimizer_step_seed=training_row.provenance.optimizer_step_seed,
            generation_binding=generation_binding,
        )


@dataclass(frozen=True)
class MemoryBudget:
    census: ParameterCensus
    allocation_bytes: int = TRAINER_ALLOCATION_BYTES
    candidate_copies: int = 2
    optimizer_moment_copies: int = 2
    activation_safety_factor: int = 2
    position_budget: int = DEFAULT_POSITION_BUDGET
    schema_version: str = MEMORY_BUDGET_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.census, ParameterCensus)
                or any(type(item) is not int or item < 1 for item in (
                    self.allocation_bytes, self.candidate_copies,
                    self.optimizer_moment_copies,
                    self.activation_safety_factor, self.position_budget))
                or self.schema_version != MEMORY_BUDGET_SCHEMA):
            _invalid("BAMF_C08_MEMORY_BUDGET_INVALID")

    @property
    def resident_bytes(self) -> int:
        # Conservative FP32 weights, two AdamW moments and candidate copies.
        return (self.census.total * FP32_BYTES
                * (1 + self.optimizer_moment_copies + self.candidate_copies))

    @property
    def digest(self) -> str:
        return _digest({
            "schema": self.schema_version,
            "topology_digest": self.census.topology_digest,
            "extents_digest": self.census.extents_digest,
            "allocation_bytes": self.allocation_bytes,
            "candidate_copies": self.candidate_copies,
            "optimizer_moment_copies": self.optimizer_moment_copies,
            "activation_safety_factor": self.activation_safety_factor,
            "position_budget": self.position_budget,
        })


def estimate_row_activation_bytes(
    row: ResourceRow, topology: ModelTopologySpecV2,
) -> int:
    """Analytical upper estimate from actual compiled/source lengths."""
    if (not isinstance(row, ResourceRow)
            or type(topology) is not ModelTopologySpecV2):
        _invalid("BAMF_C08_ACTIVATION_ARGUMENT_INVALID")
    stats = row.frame_stats
    if stats.compiled_positions + row.target_decisions > topology.context:
        _invalid("BAMF_C08_COMPILED_CONTEXT_EXCEEDED")
    per_position = (
        4 * topology.width
        + topology.query_heads * topology.head_dimension
        + 2 * topology.kv_heads * topology.head_dimension
        + 2 * topology.ffn_dimension
        + topology.convolution_kernel * topology.width
    )
    layer_elements = (
        stats.compiled_positions * per_position * topology.layers)
    frame_elements = sum(stats.frame_lengths) * topology.width
    constituent_elements = (
        stats.constituent_expansions * topology.width * 2)
    depth_elements = (
        stats.depth_summaries * topology.width * topology.depth_groups)
    target_elements = row.target_decisions * topology.width
    return FP32_BYTES * (
        layer_elements + frame_elements + constituent_elements
        + depth_elements + target_elements)


@dataclass(frozen=True)
class BatchPlan:
    groups: tuple[tuple[int, ...], ...]
    logical_row_ids: tuple[str, ...]
    microbatch_size: int
    estimated_peak_bytes: int
    resident_bytes: int
    optimizer_step_seed: int
    generation_binding: str
    topology_digest: str
    memory_budget_digest: str
    source_digest: str
    schema_version: str = BATCH_PLAN_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.microbatch_size) is not int
                or self.microbatch_size not in MICROBATCH_SIZES
                or not isinstance(self.groups, tuple)
                or not isinstance(self.logical_row_ids, tuple)):
            _invalid("BAMF_C08_BATCH_PLAN_INVALID")
        flattened = tuple(index for group in self.groups for index in group)
        if (not isinstance(self.groups, tuple) or not self.groups
                or any(not isinstance(group, tuple) or not group
                       or len(group) > self.microbatch_size
                       for group in self.groups)
                or any(type(index) is not int for index in flattened)
                or flattened != tuple(range(len(self.logical_row_ids)))
                or not self.logical_row_ids
                or any(not isinstance(row_id, str) or not row_id
                       for row_id in self.logical_row_ids)
                or len(set(self.logical_row_ids)) != len(self.logical_row_ids)
                or any(type(item) is not int or item < 0 for item in (
                    self.estimated_peak_bytes, self.resident_bytes,
                    self.optimizer_step_seed))
                or not isinstance(self.generation_binding, str)
                or not self.generation_binding
                or not all(_sha(item) for item in (
                    self.topology_digest, self.memory_budget_digest,
                    self.source_digest))
                or self.schema_version != BATCH_PLAN_SCHEMA):
            _invalid("BAMF_C08_BATCH_PLAN_INVALID")


def plan_microbatches(
    delivered_rows: tuple[ResourceRow, ...],
    topology: ModelTopologySpecV2,
    memory_budget: MemoryBudget,
    *,
    max_microbatch_size: int | None = None,
) -> BatchPlan:
    """One logical teacher visit, deterministic contiguous source partition."""
    if (not isinstance(delivered_rows, tuple) or not delivered_rows
            or any(not isinstance(row, ResourceRow) for row in delivered_rows)
            or type(topology) is not ModelTopologySpecV2
            or not isinstance(memory_budget, MemoryBudget)
            or memory_budget.census.topology_digest != topology.digest):
        _invalid("BAMF_C08_PLAN_ARGUMENT_INVALID")
    if (max_microbatch_size is not None
            and max_microbatch_size not in MICROBATCH_SIZES):
        _invalid("BAMF_C08_MICROBATCH_SIZE_INVALID")
    row_ids = tuple(row.row_id for row in delivered_rows)
    seeds = {row.optimizer_step_seed for row in delivered_rows}
    generations = {row.generation_binding for row in delivered_rows}
    if len(set(row_ids)) != len(row_ids) or len(seeds) != 1 or len(generations) != 1:
        _invalid("BAMF_C08_LOGICAL_BATCH_IDENTITY_DRIFT")
    estimates = tuple(
        estimate_row_activation_bytes(row, topology)
        for row in delivered_rows)
    resident = memory_budget.resident_bytes
    chosen = None
    for size in MICROBATCH_SIZES:
        if max_microbatch_size is not None and size > max_microbatch_size:
            continue
        groups = tuple(
            tuple(range(start, min(start + size, len(delivered_rows))))
            for start in range(0, len(delivered_rows), size))
        peaks = tuple(
            resident + memory_budget.activation_safety_factor
            * sum(estimates[index] for index in group)
            for group in groups)
        if (all(peak <= memory_budget.allocation_bytes for peak in peaks)
                and all(sum(delivered_rows[index].frame_stats.compiled_positions
                            for index in group)
                        <= memory_budget.position_budget for group in groups)):
            chosen = (size, groups, max(peaks))
            break
    if chosen is None:
        _invalid("BAMF_C08_BUDGET_EXHAUSTED")
    size, groups, peak = chosen
    return BatchPlan(
        groups=groups,
        logical_row_ids=row_ids,
        microbatch_size=size,
        estimated_peak_bytes=peak,
        resident_bytes=resident,
        optimizer_step_seed=next(iter(seeds)),
        generation_binding=next(iter(generations)),
        topology_digest=topology.digest,
        memory_budget_digest=memory_budget.digest,
        source_digest=_digest(tuple(asdict(row) for row in delivered_rows)),
    )


def indices_for_plan(plan: BatchPlan) -> tuple[tuple[int, ...], ...]:
    if not isinstance(plan, BatchPlan):
        _invalid("BAMF_C08_BATCH_PLAN_INVALID")
    return plan.groups


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
