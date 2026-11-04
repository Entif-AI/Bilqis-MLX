"""C08.1 topology-aware activation estimates and microbatch planning."""
from __future__ import annotations

from dataclasses import asdict

from ..model_topology_v2 import ModelTopologySpecV2
from .contracts import (
    FP32_BYTES, MICROBATCH_SIZES, BatchPlan, MemoryBudget, ResourceRow,
    _digest, _invalid,
)

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
