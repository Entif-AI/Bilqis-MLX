"""Pre-autodiff route selection and timing for B11 logical microbatches."""
from __future__ import annotations

import time


def gradient_path(
        backend, params, batch, row_batches, answer_plans, targets, masks,
        generation, cache, rebind_execution, salience_supervision, snapshot,
        salience_labels, *, prepare_refinement_selections,
        route_microbatch_compatible, microbatch_trace_preflight,
        prepare_route_microbatch_kernel):
    timings = {}
    started = time.perf_counter()
    refinement = prepare_refinement_selections(
        row_batches, answer_plans, generation)
    timings["b11_refinement_selection_wall_seconds"] = time.perf_counter() - started
    started = time.perf_counter()
    route_vectorized = route_microbatch_compatible(
        row_batches, answer_plans, targets, masks)
    timings["b11_route_compatibility_wall_seconds"] = time.perf_counter() - started
    if not route_vectorized:
        from bilqis_mlx.runtime.b11_source_execution_authority import (
            b11_source_authority_launch_epoch,
        )
        started = time.perf_counter()
        with b11_source_authority_launch_epoch(row_batches):
            preflight = microbatch_trace_preflight(
                backend, params, batch, row_batches, answer_plans, targets, masks,
                generation, cache, rebind_execution, salience_supervision, snapshot)
        timings["b11_fallback_trace_preflight_wall_seconds"] = (
            time.perf_counter() - started)
        timings["b11_route_kernel_prepare_wall_seconds"] = 0.0
        return False, preflight, None, None, timings
    started = time.perf_counter()
    kernel = prepare_route_microbatch_kernel(
        row_batches, answer_plans, targets, masks, None, salience_labels)
    timings["b11_route_kernel_prepare_wall_seconds"] = time.perf_counter() - started
    timings["b11_fallback_trace_preflight_wall_seconds"] = 0.0
    return True, None, refinement, kernel, timings


__all__ = ("gradient_path",)

