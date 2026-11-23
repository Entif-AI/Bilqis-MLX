#!/usr/bin/env python3
"""Disposable C05 profile for the currently unmeasured solver preparation gap."""
from __future__ import annotations

import json
import time
from unittest.mock import patch

import bilqis_mlx.runtime.capability_retention as retention
import bilqis_mlx.runtime.factory_complete_solver as factory_solver
from bilqis_mlx.runtime.tests.capability.factory.retention import (
    retention_throughput_profile as profile,
)


def main() -> int:
    build_globals = factory_solver.factory_complete_solver.__globals__
    builder_cls = factory_solver.build_factory_complete_solver.__globals__[
        "_FactoryCompleteSolverBuilder"]
    original_bind = build_globals["bind_factory_evaluation_case"]
    original_plan = build_globals["task_goal_route_plan"]
    original_outputs = build_globals["batched_factory_outputs"]
    original_prepare = builder_cls.prepare
    original_context_from = builder_cls.context_from
    original_measure = retention.CompleteSolver._measure

    bind_seconds: list[float] = []
    plan_seconds: list[float] = []
    batched_output_seconds: list[float] = []
    prepare_seconds: list[float] = []
    context_from_seconds: list[float] = []
    measure_seconds: list[float] = []

    def timed(bucket, fn):
        def wrapped(*args, **kwargs):
            started = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                bucket.append(max(0.0, time.perf_counter() - started))
        return wrapped

    with patch.dict(
            build_globals,
            {
                "bind_factory_evaluation_case": timed(bind_seconds, original_bind),
                "task_goal_route_plan": timed(plan_seconds, original_plan),
                "batched_factory_outputs": timed(
                    batched_output_seconds, original_outputs),
            }), patch.object(
                builder_cls, "prepare",
                timed(prepare_seconds, original_prepare)), patch.object(
                    builder_cls, "context_from",
                    timed(context_from_seconds, original_context_from)), patch.object(
                        retention.CompleteSolver, "_measure",
                        timed(measure_seconds, original_measure)):
        result = profile.main()

    print("ISSUE1566_C05_SOLVER_GAP_SPLIT " + json.dumps({
        "schema": "bilqis.bamf.issue1566-c05-solver-gap-split/v1",
        "bind_seconds": bind_seconds,
        "plan_seconds": plan_seconds,
        "batched_output_seconds": batched_output_seconds,
        "prepare_seconds": prepare_seconds,
        "context_from_seconds": context_from_seconds,
        "measure_seconds": measure_seconds,
        "bind_total_seconds": sum(bind_seconds),
        "plan_total_seconds": sum(plan_seconds),
        "batched_output_total_seconds": sum(batched_output_seconds),
        "prepare_total_seconds": sum(prepare_seconds),
        "context_from_total_seconds": sum(context_from_seconds),
        "measure_total_seconds": sum(measure_seconds),
    }, sort_keys=True), flush=True)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
