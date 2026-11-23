"""Contracts and shared accounting helpers for C08 logical-batch gradients."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.atlas_resources import DistributedStepManifest


_ISSUER = object()
_LOGICAL_BATCH_MIN_ROWS = 2
_SHA256_HEX_LENGTH = 64


def _invalid(reason: str) -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID, reason=reason)


@dataclass(frozen=True)
class DistributedLogicalBatchMetadata:
    """Execution-only distributed facts; excluded from logical/model identity."""
    manifest: DistributedStepManifest
    compute_seconds_per_worker: tuple[float, ...]
    communication_seconds: float
    peak_memory_per_worker: tuple[int, ...]
    training_authorities: tuple = ()

    def __post_init__(self) -> None:
        if (type(self.manifest) is not DistributedStepManifest
                or type(self.compute_seconds_per_worker) is not tuple
                or len(self.compute_seconds_per_worker) != self.manifest.world_size
                or any(type(value) is not float or value < 0.0
                       for value in self.compute_seconds_per_worker)
                or type(self.communication_seconds) is not float
                or self.communication_seconds < 0.0
                or type(self.peak_memory_per_worker) is not tuple
                or len(self.peak_memory_per_worker) != self.manifest.world_size
                or any(type(value) is not int or value < 0
                       for value in self.peak_memory_per_worker)
                or type(self.training_authorities) is not tuple):
            _invalid("C08_DISTRIBUTED_LOGICAL_METADATA_INVALID")
        self.manifest.__post_init__()


@dataclass(frozen=True, init=False)
class LogicalBatchGradientExecution:
    """Owner-issued raw mean gradient plus every row-scoped B11 loss execution."""

    loss_executions: tuple
    gradients: Mapping
    weighted_mean_loss: mx.array
    source_digest: str
    generation_binding: str
    plan_digest: str
    gradient_launches: int
    vectorized_microbatches: int
    materialization_barriers: int
    scalar_fallback_rows: int
    wall_seconds: float
    distributed_metadata: DistributedLogicalBatchMetadata | None = field(
        default=None, repr=False, compare=False)
    _numerical_finite_attested: bool = field(init=False, repr=False, compare=False)
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid("C08_LOGICAL_BATCH_GRADIENT_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self):
        if (getattr(self, "_issuance", None) is not _ISSUER
                or type(self.loss_executions) is not tuple
                or len(self.loss_executions) < _LOGICAL_BATCH_MIN_ROWS
                or not isinstance(self.gradients, Mapping)
                or not self.gradients
                or any(not isinstance(value, mx.array)
                       for value in self.gradients.values())
                or not isinstance(self.weighted_mean_loss, mx.array)
                or self.weighted_mean_loss.size != 1
                or type(getattr(self, "_numerical_finite_attested", None)) is not bool
                or not isinstance(self.source_digest, str)
                or not self.source_digest
                or not isinstance(self.generation_binding, str)
                or not self.generation_binding
                or not isinstance(self.plan_digest, str)
                or len(self.plan_digest) != _SHA256_HEX_LENGTH
                or any(char not in "0123456789abcdef" for char in self.plan_digest)
                or type(self.gradient_launches) is not int
                or self.gradient_launches < 1
                or type(self.vectorized_microbatches) is not int
                or not 0 <= self.vectorized_microbatches <= self.gradient_launches
                or type(self.materialization_barriers) is not int
                or self.materialization_barriers != 1
                or type(self.scalar_fallback_rows) is not int
                or not 0 <= self.scalar_fallback_rows <= len(self.loss_executions)
                or type(self.wall_seconds) is not float
                or self.wall_seconds < 0.0
                or (self.distributed_metadata is not None
                    and type(self.distributed_metadata)
                    is not DistributedLogicalBatchMetadata)):
            _invalid("C08_LOGICAL_BATCH_GRADIENT_INVALID")
        if (not getattr(self, "_numerical_finite_attested", False)
                and not bool(mx.all(mx.isfinite(self.weighted_mean_loss)))):
            _invalid("C08_LOGICAL_BATCH_GRADIENT_INVALID")
        if self.distributed_metadata is not None:
            self.distributed_metadata.__post_init__()
            if self.distributed_metadata.manifest.logical_batch_digest != self.plan_digest:
                _invalid("C08_DISTRIBUTED_LOGICAL_METADATA_PLAN_DRIFT")


def require_logical_batch_gradient_execution(value):
    if type(value) is not LogicalBatchGradientExecution:
        _invalid("C08_LOGICAL_BATCH_GRADIENT_REQUIRED")
    value.__post_init__()
    return value


def _sum_tree(total, gradients):
    if total is None:
        return {name: value for name, value in gradients.items()}
    if set(total) != set(gradients):
        _invalid("C08_LOGICAL_BATCH_GRADIENT_TREE_DRIFT")
    return {name: total[name] + gradients[name] for name in total}


def _scale_tree(gradients, scale: float):
    return {name: value * mx.array(scale, dtype=value.dtype)
            for name, value in gradients.items()}


def _add_b11_observation(total: dict, execution) -> None:
    observed = getattr(execution, "_performance_observation", None)
    if not isinstance(observed, dict):
        return
    for name in (
        "b11_preflight_wall_seconds", "b11_finite_validation_wall_seconds",
        "b11_execution_rebinding_wall_seconds", "b11_refinement_selection_wall_seconds",
        "b11_route_compatibility_wall_seconds", "b11_route_kernel_prepare_wall_seconds",
        "b11_fallback_trace_preflight_wall_seconds", "b11_preflight_other_wall_seconds",
        "b11_autodiff_wall_seconds", "b11_autodiff_dispatch_wall_seconds",
        "b11_autodiff_dispatch_rebind_wall_seconds",
        "b11_autodiff_dispatch_source_producer_wall_seconds",
        "b11_autodiff_dispatch_source_hidden_graph_wall_seconds",
        "b11_autodiff_dispatch_refinement_graph_wall_seconds",
        "b11_autodiff_dispatch_route_graph_wall_seconds",
        "b11_autodiff_dispatch_transform_other_wall_seconds",
        "b11_autodiff_materialization_wall_seconds", "b11_route_evidence_wall_seconds",
        "b11_autodiff_other_wall_seconds", "b11_gradient_finite_validation_wall_seconds",
        "b11_postflight_validation_wall_seconds",
        "b11_postflight_trajectory_validation_wall_seconds",
        "b11_postflight_output_attestation_wall_seconds",
        "b11_postflight_loss_validation_wall_seconds",
        "b11_postflight_gradient_structure_wall_seconds",
        "b11_postflight_result_construction_wall_seconds",
    ):
        total[name] += float(observed.get(name, 0.0))
    for name in (
        "b11_materialization_barrier_count", "b11_host_readback_count",
        "b11_validation_sync_count", "b11_provider_draw_count",
        "b11_atlas_reload_count",
    ):
        total[name] += int(observed.get(name, 0))


__all__ = (
    "DistributedLogicalBatchMetadata", "LogicalBatchGradientExecution",
    "require_logical_batch_gradient_execution",
)
