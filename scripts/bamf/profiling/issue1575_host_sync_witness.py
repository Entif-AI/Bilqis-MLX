#!/usr/bin/env python3
"""Run matched disposable 32-row #1575 candidate witnesses in two source trees."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


CHILD = r'''
import json
import os
from pathlib import Path
import tempfile
import time
from collections.abc import Mapping
from contextlib import nullcontext
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.runtime.mlx_memory import training_memory_policy
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.teacher_observation_capture import ObservationCapture
from bilqis_mlx.runtime.tests.capability.factory.retention import retention_throughput_profile as p
from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import retained_digest

root = Path.cwd()
artifact = (root / os.environ["ISSUE1575_ARTIFACT_REL"]).resolve()
source = (root / "vendor/legacy-v16").resolve()
rows_requested = int(os.environ["ISSUE1575_ROWS"])
label = os.environ["ISSUE1575_LABEL"]
if not artifact.is_dir() or not source.is_dir():
    raise SystemExit("#1575 witness requires checked-in Atlas and legacy source fixtures")

previous = mx.default_device()
mx.set_default_device(mx.gpu)
try:
    original_delivery = ObservationCapture.delivery
    original_value_and_grad = mx.value_and_grad

    def compatible_delivery(self, *args, fresh_support=(), **kwargs):
        if fresh_support:
            raise AssertionError(
                "#1575 witness compatibility shim refuses non-empty fresh support")
        return original_delivery(self, *args, **kwargs)

    def compatible_value_and_grad(*args, **kwargs):
        transformed = original_value_and_grad(*args, **kwargs)

        def invoke(parameters, *call_args, **call_kwargs):
            if type(parameters) is not dict and isinstance(parameters, Mapping):
                parameters = dict(parameters)
            return transformed(parameters, *call_args, **call_kwargs)

        return invoke

    control_autodiff_compatibility = (
        patch.object(mx, "value_and_grad", compatible_value_and_grad)
        if label == "base" else nullcontext())

    with training_memory_policy(mx):
        with tempfile.TemporaryDirectory() as directory, p.host_source_authority_patch(), \
                patch.object(ObservationCapture, "delivery", compatible_delivery), \
                control_autodiff_compatibility:
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
                    _bound, rows, step = p._train_candidate(
                        run_dir, parent, source_context, feature_path, artifact,
                        "B.AND", rows_requested)
                mx.synchronize()
                wall = max(0.0, time.perf_counter() - started)
                cost = dict(step.realized_cost)
                keys = (
                    "candidate_step_wall_seconds",
                    "b11_autodiff_materialization_wall_seconds",
                    "b11_materialization_barrier_count",
                    "b11_host_readback_count",
                    "b11_validation_sync_count",
                    "c08_materialization_barriers",
                    "c08_gradient_launches",
                    "c08_vectorized_microbatches",
                    "c08_scalar_fallback_rows",
                    "loss_total",
                )
                print("ISSUE1575_RESULT " + json.dumps({
                    "label": label,
                    "logical_rows": len(rows),
                    "requested_rows": rows_requested,
                    "wall_seconds": wall,
                    "optimizer_state_sha256": retained_digest(step.transaction),
                    "optimizer_step": (
                        step.transaction.parent.optimizer_step
                        + step.transaction.update_steps),
                    "realized_cost": {key: cost.get(key) for key in keys},
                }, sort_keys=True), flush=True)
finally:
    mx.set_default_device(previous)
'''


def _run(label: str, root: Path, rows: int, artifact_rel: str) -> dict:
    environment = os.environ.copy()
    environment.update({
        "BILQIS_TEST_WORKERS": "1",
        "ISSUE1575_ARTIFACT_REL": artifact_rel,
        "ISSUE1575_LABEL": label,
        "ISSUE1575_ROWS": str(rows),
    })
    process = subprocess.Popen(
        [sys.executable, "-B", "-c", CHILD], cwd=root, env=environment,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
    lines = []
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="", flush=True)
        if line.startswith("ISSUE1575_RESULT "):
            lines.append(line.rstrip())
    returncode = process.wait()
    if returncode != 0:
        raise SystemExit(f"{label}: child failed with return code {returncode}")
    if len(lines) != 1:
        raise SystemExit(f"{label}: expected exactly one #1575 result")
    return json.loads(lines[0].split(" ", 1)[1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--feature", type=Path, required=True)
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--feature-commit", required=True)
    parser.add_argument("--rows", type=int, default=32)
    parser.add_argument(
        "--only", choices=("base", "feature", "both"), default="both")
    parser.add_argument(
        "--artifact-rel",
        default=("bilqis_mlx/bootstrap_assets/atlas/"
                 "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7"))
    args = parser.parse_args()
    if args.rows != 32:
        raise SystemExit("#1575 acceptance witness is fixed at 32 logical rows")
    base_commit = subprocess.run(
        ["git", "-C", str(args.base), "rev-parse", "HEAD"], check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    base_dirty = subprocess.run(
        ["git", "-C", str(args.base), "status", "--porcelain"], check=True,
        text=True, stdout=subprocess.PIPE).stdout.strip()
    if base_commit != args.base_commit or base_dirty:
        raise SystemExit("#1575 base worktree identity or cleanliness drifted")
    if args.only == "base":
        base = _run("base", args.base.resolve(), args.rows, args.artifact_rel)
        print("ISSUE1575_SINGLE " + json.dumps({
            "schema": "bilqis.bamf.issue1575-host-sync-single/v1",
            "base_commit": args.base_commit,
            "result": base,
        }, sort_keys=True), flush=True)
        return 0
    if args.only == "feature":
        feature = _run("feature", args.feature.resolve(), args.rows, args.artifact_rel)
        print("ISSUE1575_SINGLE " + json.dumps({
            "schema": "bilqis.bamf.issue1575-host-sync-single/v1",
            "feature_commit": args.feature_commit,
            "feature_snapshot_sha256": os.environ.get("BILQIS_DETACHED_SOURCE_SHA256"),
            "result": feature,
        }, sort_keys=True), flush=True)
        return 0
    base = _run("base", args.base.resolve(), args.rows, args.artifact_rel)
    feature = _run("feature", args.feature.resolve(), args.rows, args.artifact_rel)
    equivalent = (
        base["logical_rows"] == feature["logical_rows"] == args.rows
        and base["optimizer_state_sha256"] == feature["optimizer_state_sha256"]
        and base["optimizer_step"] == feature["optimizer_step"]
        and base["realized_cost"]["loss_total"] == feature["realized_cost"]["loss_total"])
    receipt = {
        "schema": "bilqis.bamf.issue1575-host-sync-witness/v1",
        "base_commit": args.base_commit,
        "feature_commit": args.feature_commit,
        "feature_snapshot_sha256": os.environ.get("BILQIS_DETACHED_SOURCE_SHA256"),
        "workload": {"capability": "B.AND", "logical_rows": args.rows,
                     "artifact_rel": args.artifact_rel},
        "base": base, "feature": feature, "equivalent": equivalent,
    }
    print("ISSUE1575_COMPARISON " + json.dumps(receipt, sort_keys=True), flush=True)
    return 0 if equivalent else 1


if __name__ == "__main__":
    raise SystemExit(main())
