#!/usr/bin/env python3
"""Matched disposable 32-row #1576 compiled/uncompiled training witness."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys


CHILD = r'''
import json
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.runtime.mlx_memory import training_memory_policy
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.teacher_observation_capture import ObservationCapture
from bilqis_mlx.runtime.tests.capability.factory.retention import retention_throughput_profile as p
from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import retained_digest

root = Path.cwd()
artifact = (root / os.environ["ISSUE1576_ARTIFACT_REL"]).resolve()
source = (root / "vendor/legacy-v16").resolve()
rows_requested = int(os.environ["ISSUE1576_ROWS"])
horizon = int(os.environ["ISSUE1576_HORIZON"])
label = os.environ["ISSUE1576_LABEL"]
if not artifact.is_dir() or not source.is_dir():
    raise SystemExit("#1576 witness requires checked-in Atlas and legacy source fixtures")

previous = mx.default_device()
mx.set_default_device(mx.gpu)
try:
    original_delivery = ObservationCapture.delivery

    def compatible_delivery(self, *args, fresh_support=(), **kwargs):
        if fresh_support:
            raise AssertionError(
                "#1576 witness compatibility shim refuses non-empty fresh support")
        return original_delivery(self, *args, **kwargs)

    with training_memory_policy(mx):
        with tempfile.TemporaryDirectory() as directory, p.host_source_authority_patch(), \
                patch.object(ObservationCapture, "delivery", compatible_delivery):
            stage = Path(directory)
            with patch.dict(os.environ, {
                    "BILQIS_A01_ATLAS_BUNDLE": str(artifact),
                    "BILQIS_ATLAS_REAL_ARTIFACT": str(artifact),
                    "BILQIS_DATA_PLANE": str(stage / "plane.sqlite3"),
            }):
                run_dir, parent, source_context = p._prepare_run(
                    stage, root, source, artifact)
                parent, source_context, _atlas_path, feature_path = p._execution_context(
                    run_dir)
                mx.clear_cache()
                mx.reset_peak_memory()
                started = time.perf_counter()
                with evidence_mode(strict=False):
                    _bound, rows, steps = p.real_candidate_training_horizon(
                        run_dir, parent, source_context, feature_path, artifact,
                        learning_rate=p.C05_TRAINING_LEARNING_RATE,
                        horizon=horizon, capability="B.AND", source_each=rows_requested)
                mx.synchronize()
                wall = max(0.0, time.perf_counter() - started)
                keys = (
                    "candidate_step_wall_seconds",
                    "b11_autodiff_dispatch_route_graph_wall_seconds",
                    "b11_autodiff_materialization_wall_seconds",
                    "b11_mlx_compile_enabled",
                    "b11_mlx_compile_cache_hit",
                    "b11_mlx_compile_cache_miss",
                    "b11_mlx_compile_cache_entries",
                    "b11_mlx_compile_cold_dispatch_wall_seconds",
                    "b11_mlx_compile_warm_dispatch_wall_seconds",
                    "b11_materialization_barrier_count",
                    "b11_host_readback_count",
                    "b11_validation_sync_count",
                    "c08_materialization_barriers",
                    "c08_gradient_launches",
                    "c08_vectorized_microbatches",
                    "c08_scalar_fallback_rows",
                    "loss_total",
                )
                samples = []
                for ordinal, step in enumerate(steps, 1):
                    cost = dict(step.realized_cost)
                    samples.append({
                        "step": ordinal,
                        **{key: cost.get(key) for key in keys},
                    })
                print("ISSUE1576_RESULT " + json.dumps({
                    "label": label,
                    "compile_enabled": os.environ["BILQIS_MLX_COMPILE_STABLE_KERNEL"] == "1",
                    "logical_rows": len(rows),
                    "requested_rows": rows_requested,
                    "horizon": horizon,
                    "wall_seconds": wall,
                    "mlx_peak_bytes": int(mx.get_peak_memory()),
                    "optimizer_state_sha256": retained_digest(steps[-1].transaction),
                    "optimizer_step": (
                        steps[-1].transaction.parent.optimizer_step
                        + steps[-1].transaction.update_steps),
                    "samples": samples,
                }, sort_keys=True), flush=True)
finally:
    mx.set_default_device(previous)
'''


def _run(label: str, root: Path, rows: int, horizon: int, artifact_rel: str) -> dict:
    environment = os.environ.copy()
    environment.update({
        "BILQIS_TEST_WORKERS": "1",
        "BILQIS_MLX_COMPILE_STABLE_KERNEL": "1" if label == "compiled" else "0",
        "ISSUE1576_ARTIFACT_REL": artifact_rel,
        "ISSUE1576_LABEL": label,
        "ISSUE1576_ROWS": str(rows),
        "ISSUE1576_HORIZON": str(horizon),
    })
    process = subprocess.run(
        [sys.executable, "-B", "-c", CHILD], cwd=root, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(process.stdout, end="", flush=True)
    if process.returncode != 0:
        raise SystemExit(f"{label}: child failed with return code {process.returncode}")
    lines = [line for line in process.stdout.splitlines()
             if line.startswith("ISSUE1576_RESULT ")]
    if len(lines) != 1:
        raise SystemExit(f"{label}: expected exactly one #1576 result")
    return json.loads(lines[0].split(" ", 1)[1])


def _median(result: dict, key: str) -> float:
    values = [float(item[key]) for item in result["samples"] if item.get(key) is not None]
    return statistics.median(values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--rows", type=int, default=32)
    parser.add_argument("--horizon", type=int, default=4)
    parser.add_argument(
        "--artifact-rel",
        default=("bilqis_mlx/bootstrap_assets/atlas/"
                 "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7"))
    args = parser.parse_args()
    if args.rows != 32 or args.horizon < 3:
        raise SystemExit("#1576 acceptance witness requires 32 rows and >=3 steps")
    root = args.root.resolve()
    control = _run("uncompiled", root, args.rows, args.horizon, args.artifact_rel)
    compiled = _run("compiled", root, args.rows, args.horizon, args.artifact_rel)
    control_losses = [item["loss_total"] for item in control["samples"]]
    compiled_losses = [item["loss_total"] for item in compiled["samples"]]
    warm = compiled["samples"][1:]
    warm_dispatch = statistics.median(float(item["b11_mlx_compile_warm_dispatch_wall_seconds"])
                                      for item in warm)
    cold_dispatch = float(compiled["samples"][0]["b11_mlx_compile_cold_dispatch_wall_seconds"])
    receipt = {
        "schema": "bilqis.bamf.issue1576-mlx-compile-witness/v1",
        "control": control,
        "compiled": compiled,
        "parity": {
            "loss_sequence_equal": control_losses == compiled_losses,
            "optimizer_state_sha256_equal": (
                control["optimizer_state_sha256"] == compiled["optimizer_state_sha256"]),
            "optimizer_step_equal": control["optimizer_step"] == compiled["optimizer_step"],
        },
        "performance": {
            "control_step_median_seconds": _median(control, "candidate_step_wall_seconds"),
            "compiled_step_median_seconds": _median(compiled, "candidate_step_wall_seconds"),
            "cold_compile_plus_dispatch_seconds": cold_dispatch,
            "warm_compiled_dispatch_median_seconds": warm_dispatch,
            "cold_compile_overhead_estimate_seconds": max(0.0, cold_dispatch - warm_dispatch),
            "control_peak_bytes": control["mlx_peak_bytes"],
            "compiled_peak_bytes": compiled["mlx_peak_bytes"],
        },
    }
    print("ISSUE1576_WITNESS " + json.dumps(receipt, sort_keys=True), flush=True)
    if not all(receipt["parity"].values()):
        raise SystemExit("#1576 compiled/uncompiled numerical or optimizer parity failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
