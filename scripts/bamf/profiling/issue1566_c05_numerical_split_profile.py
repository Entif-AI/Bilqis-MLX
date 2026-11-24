#!/usr/bin/env python3
"""Disposable C05 profile splitting backbone materialization from route/readout."""
from __future__ import annotations

import json
import time
from unittest.mock import patch

import mlx.core as mx

import bilqis_mlx.runtime.factory_evaluation_batching as batching
from bilqis_mlx.runtime.tests.capability.factory.retention import (
    retention_throughput_profile as profile,
)


def main() -> int:
    original_finalize = batching.finalize_source_backbone_hidden
    execution_globals = batching._execute_chunk.__globals__
    original_route = execution_globals["route_microbatch_trajectory"]
    backbone_seconds: list[float] = []
    route_seconds: list[float] = []

    def materialized_backbone(producer):
        started = time.perf_counter()
        hidden = original_finalize(producer)
        mx.eval(hidden)
        backbone_seconds.append(max(0.0, time.perf_counter() - started))
        return hidden

    def materialized_route(parameters, hidden, kernel):
        started = time.perf_counter()
        trajectory, route_logits = original_route(parameters, hidden, kernel)
        mx.eval(*trajectory, *route_logits)
        route_seconds.append(max(0.0, time.perf_counter() - started))
        return trajectory, route_logits

    with patch.dict(
            execution_globals,
            {
                "finalize_source_backbone_hidden": materialized_backbone,
                "route_microbatch_trajectory": materialized_route,
            }):
        result = profile.main()

    print("ISSUE1566_C05_NUMERICAL_SPLIT " + json.dumps({
        "schema": "bilqis.bamf.issue1566-c05-numerical-split/v1",
        "backbone_materialization_seconds": backbone_seconds,
        "route_materialization_seconds": route_seconds,
        "backbone_total_seconds": sum(backbone_seconds),
        "route_total_seconds": sum(route_seconds),
    }, sort_keys=True), flush=True)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
