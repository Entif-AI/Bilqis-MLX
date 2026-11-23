#!/usr/bin/env python3
"""Run one disposable #1578 physical-geometry arm."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mlx.core as mx

from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.factory_training_bridge import LearningFirstPreparationCache
import bilqis_mlx.runtime.factory_candidate_components as components
from bilqis_mlx.runtime.mlx_memory import training_memory_policy
from bilqis_mlx.runtime.teacher_observation_capture import ObservationCapture
import bilqis_mlx.runtime.tests.capability.factory.owner.bamf_c16_2c_witness_support as c16
from bilqis_mlx.runtime.tests.capability.factory.retention import (
    retention_throughput_profile as profile,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import retained_digest


def _compatible_delivery(original):
    def delivery(self, *args, fresh_support=(), **kwargs):
        if fresh_support:
            raise AssertionError(
                "#1578 physical witness refuses non-empty fresh support"
            )
        return original(self, *args, **kwargs)

    return delivery


def _run_arm(root, artifact, source, logical_rows, physical_cap):
    cache = LearningFirstPreparationCache()
    original_train = c16.train_bamf_factory_step

    def train_with_cache(*args, **kwargs):
        kwargs["learning_first_cache"] = cache
        return original_train(*args, **kwargs)

    allowed = tuple(
        size for size in (32, 16, 8, 4, 2, 1) if size <= physical_cap
    )
    with training_memory_policy(mx):
        with (
            tempfile.TemporaryDirectory() as directory,
            profile.host_source_authority_patch(),
            patch.object(
                ObservationCapture,
                "delivery",
                _compatible_delivery(ObservationCapture.delivery),
            ),
            patch.object(
                c16,
                "train_bamf_factory_step",
                side_effect=train_with_cache,
            ),
            patch.object(components, "MICROBATCH_SIZES", allowed),
        ):
            stage = Path(directory)
            with patch.dict(
                os.environ,
                {
                    "BILQIS_A01_ATLAS_BUNDLE": str(artifact),
                    "BILQIS_ATLAS_REAL_ARTIFACT": str(artifact),
                    "BILQIS_DATA_PLANE": str(stage / "plane.sqlite3"),
                },
            ):
                run_dir, parent, source_context = profile._prepare_run(
                    stage, root, source, artifact
                )
                (
                    parent,
                    source_context,
                    _atlas_path,
                    feature_path,
                ) = profile._execution_context(run_dir)
                mx.clear_cache()
                mx.reset_peak_memory()
                started = time.perf_counter()
                with evidence_mode(strict=False):
                    _bound, rows, step = profile._train_candidate(
                        run_dir,
                        parent,
                        source_context,
                        feature_path,
                        artifact,
                        "B.AND",
                        logical_rows,
                    )
                mx.synchronize()
                return rows, step, dict(step.realized_cost), started


def _result(rows, step, cost, physical_cap, started):
    return {
        "logical_batch_size": len(rows),
        "physical_cap": physical_cap,
        "physical_microbatch_size": cost.get("c08_microbatch_size"),
        "physical_microbatch_count": cost.get("c08_microbatch_count"),
        "gradient_launches": cost.get("c08_gradient_launches"),
        "rows_per_launch": cost.get("c08_rows_per_gradient_launch"),
        "estimated_peak_bytes": cost.get("c08_estimated_peak_bytes"),
        "memory_budget_bytes": cost.get("c08_memory_budget_bytes"),
        "actual_mlx_peak_bytes": int(mx.get_peak_memory()),
        "candidate_step_wall_seconds": cost.get("candidate_step_wall_seconds"),
        "c08_logical_batch_wall_seconds": cost.get(
            "c08_logical_batch_wall_seconds"
        ),
        "c08_group_execution_wall_seconds": cost.get(
            "c08_group_execution_wall_seconds"
        ),
        "c08_aggregation_wall_seconds": cost.get("c08_aggregation_wall_seconds"),
        "c08_final_materialization_wall_seconds": cost.get(
            "c08_final_materialization_wall_seconds"
        ),
        "b11_autodiff_materialization_wall_seconds": cost.get(
            "b11_autodiff_materialization_wall_seconds"
        ),
        "loss_total": cost.get("loss_total"),
        "optimizer_state_sha256": retained_digest(step.transaction),
        "optimizer_step": (
            step.transaction.parent.optimizer_step + step.transaction.update_steps
        ),
        "wall_seconds": max(0.0, time.perf_counter() - started),
    }


def main() -> int:
    root = Path.cwd()
    artifact = (root / os.environ["ISSUE1578_ARTIFACT_REL"]).resolve()
    source = (root / "vendor/legacy-v16").resolve()
    logical_rows = int(os.environ["ISSUE1578_LOGICAL_ROWS"])
    physical_cap = int(os.environ["ISSUE1578_PHYSICAL_CAP"])
    if not artifact.is_dir() or not source.is_dir():
        raise SystemExit(
            "#1578 witness requires checked-in Atlas and legacy source fixtures"
        )

    previous = mx.default_device()
    mx.set_default_device(mx.gpu)
    try:
        rows, step, cost, started = _run_arm(
            root, artifact, source, logical_rows, physical_cap
        )
        print(
            "ISSUE1578_PHYSICAL_RESULT "
            + json.dumps(
                _result(rows, step, cost, physical_cap, started), sort_keys=True
            ),
            flush=True,
        )
    finally:
        mx.set_default_device(previous)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
