"""C08.1 pure topology-aware memory and one-step gradient plan.

This owner consumes measured compiler frame statistics and B01's parameter
census. It does not allocate MLX arrays or acquire optimizer write authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Callable

from ...errors import ErrorBus, SCHOOL
from ..model_topology_v2 import ModelTopologySpecV2, ParameterCensus
from ..atlas_training_contracts import _canonical_digest


FRAME_STATS_SCHEMA = "bilqis.c08.frame-stats/v1"
RESOURCE_ROW_SCHEMA = "bilqis.c08.resource-row/v2"
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
    training_row_sha256: str
    delivered_content_sha256: str
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
                or not _sha(self.training_row_sha256)
                or not _sha(self.delivered_content_sha256)
                or self.schema_version != RESOURCE_ROW_SCHEMA):
            _invalid("BAMF_C08_RESOURCE_ROW_INVALID")

    @classmethod
    def from_training_row(
        cls, training_row: object, frame_stats: FrameStats,
        *, generation_binding: str, delivered_content_sha256: str,
    ) -> "ResourceRow":
        """Bind exact C02 delivery identity to A05-owned compiler statistics."""
        from ..atlas_training_adapter import BamfTrainingRow

        if (not _sha(delivered_content_sha256)
                or not isinstance(training_row, BamfTrainingRow)
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
            training_row_sha256=_canonical_digest(
                training_row, trailing_newline=True),
            delivered_content_sha256=delivered_content_sha256,
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

    @property
    def digest(self) -> str:
        """Content identity of the exact deterministic microbatch plan."""
        return _digest({
            "groups": self.groups,
            "logical_row_ids": self.logical_row_ids,
            "microbatch_size": self.microbatch_size,
            "estimated_peak_bytes": self.estimated_peak_bytes,
            "resident_bytes": self.resident_bytes,
            "optimizer_step_seed": self.optimizer_step_seed,
            "generation_binding": self.generation_binding,
            "topology_digest": self.topology_digest,
            "memory_budget_digest": self.memory_budget_digest,
            "source_digest": self.source_digest,
            "schema_version": self.schema_version,
        })
