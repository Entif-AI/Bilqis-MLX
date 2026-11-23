#!/usr/bin/env python3
"""Disposable Metal witness for the #1566 strict-mode execution boundary.

The witness creates a temporary BAMF run, measures one cold learning-first
accepted-session snapshot and its same-generation reuse, executes one genuine
32-row Metal candidate step without publishing it, then measures strict-mode
snapshot loading twice as a control. It never mutates a human learner.
"""
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

from bilqis_mlx.runtime.teacher_observation_capture import ObservationCapture
from bilqis_mlx.runtime.bamf_operator.session import _SessionExecutionContext
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.bamf_operator.session_parts.session_support import _execution_context
from bilqis_mlx.runtime.mlx_memory import training_memory_policy
from bilqis_mlx.runtime.tests.capability.factory.retention import (
    retention_throughput_profile as profile,
)


SCHEMA = "bilqis.bamf.issue1566-strict-mode-boundary-witness/v1"
ROWS = 32


def _artifact(root: Path) -> Path:
    raw = os.environ.get("BILQIS_A01_ATLAS_BUNDLE")
    if raw:
        artifact = Path(raw).resolve()
    else:
        artifact = (
            root
            / "bilqis_mlx/bootstrap_assets/atlas"
            / "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7"
        ).resolve()
    if not artifact.is_dir():
        raise SystemExit(f"#1566 witness Atlas fixture is missing: {artifact}")
    return artifact


def _reset_process_caches() -> None:
    from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
        _reset_execution_cache_owner_for_tests,
    )

    _reset_execution_cache_owner_for_tests()


def _timed_snapshot(snapshot, run_dir: Path, metrics: dict | None = None):
    started = time.perf_counter()
    result = snapshot(run_dir, performance_metrics=metrics)
    return result, max(0.0, time.perf_counter() - started)


def _compatibility_delivery(original_delivery):
    def compatible_delivery(self, *args, fresh_support=(), **kwargs):
        if fresh_support:
            raise AssertionError(
                "#1566 witness compatibility shim refuses non-empty fresh support")
        return original_delivery(self, *args, **kwargs)
    return compatible_delivery


def _measure_learning_first(run_dir: Path, artifact: Path, loader_calls: dict):
    accepted_state_metrics: dict[str, float] = {}

    def loader(path, **kwargs):
        loader_calls["learning_first"] += 1
        return _execution_context(path, **kwargs)

    with evidence_mode(strict=False):
        ordinary = _SessionExecutionContext(strict=False, loader=loader)
        first, first_wall = _timed_snapshot(
            ordinary, run_dir, accepted_state_metrics)
        second, second_wall = _timed_snapshot(ordinary, run_dir, {})
        if second is not first or loader_calls["learning_first"] != 1:
            raise AssertionError("learning-first session snapshot was not reused")
        parent, source_context, _atlas_path, feature_path = first
        mx.clear_cache()
        mx.reset_peak_memory()
        training_started = time.perf_counter()
        _bound, rows, step = profile._train_candidate(
            run_dir, parent, source_context, feature_path, artifact, "B.AND", ROWS)
        mx.synchronize()
    return {
        "rows": rows,
        "step": step,
        "accepted_state_metrics": accepted_state_metrics,
        "first_wall": first_wall,
        "second_wall": second_wall,
        "training_wall": max(0.0, time.perf_counter() - training_started),
    }


def _measure_strict(run_dir: Path, loader_calls: dict):
    def loader(path, **kwargs):
        loader_calls["strict"] += 1
        return _execution_context(path, **kwargs)

    with evidence_mode(strict=True):
        strict = _SessionExecutionContext(strict=True, loader=loader)
        _first, first_wall = _timed_snapshot(strict, run_dir, {})
        _second, second_wall = _timed_snapshot(strict, run_dir, {})
    if loader_calls["strict"] != 2:
        raise AssertionError("strict mode did not re-enter accepted-state loader")
    return first_wall, second_wall


def _receipt(learning, strict_walls, loader_calls: dict) -> dict:
    step = learning["step"]
    cost = dict(step.realized_cost)
    return {
        "schema": SCHEMA,
        "authorizing": False,
        "published": False,
        "human_run_mutated": False,
        "capability": "B.AND",
        "logical_rows": len(learning["rows"]),
        "learning_first": {
            "accepted_session_loader_calls": loader_calls["learning_first"],
            "cold_session_setup_wall_seconds": learning["first_wall"],
            "same_generation_reuse_wall_seconds": learning["second_wall"],
            "accepted_state_metrics": learning["accepted_state_metrics"],
            "candidate_training_wall_seconds": learning["training_wall"],
            "candidate_step_wall_seconds": cost.get("candidate_step_wall_seconds"),
            "optimizer_updates": step.transaction.update_steps,
        },
        "strict_control": {
            "accepted_session_loader_calls": loader_calls["strict"],
            "first_setup_wall_seconds": strict_walls[0],
            "second_setup_wall_seconds": strict_walls[1],
        },
        "mlx_peak_bytes": int(mx.get_peak_memory()),
        "mlx_default_device": str(mx.default_device()),
    }


def _run_witness(root: Path, source: Path, artifact: Path) -> dict:
    compatible_delivery = _compatibility_delivery(ObservationCapture.delivery)
    with training_memory_policy(mx):
        with tempfile.TemporaryDirectory() as directory, profile.host_source_authority_patch(), \
                patch.object(ObservationCapture, "delivery", compatible_delivery):
            stage = Path(directory)
            with patch.dict(os.environ, {
                "BILQIS_A01_ATLAS_BUNDLE": str(artifact),
                "BILQIS_ATLAS_REAL_ARTIFACT": str(artifact),
                "BILQIS_DATA_PLANE": str(stage / "plane.sqlite3"),
                "BILQIS_C05_PROFILE_CANDIDATE_HORIZON": "1",
            }):
                run_dir, _parent, _context = profile._prepare_run(
                    stage, root, source, artifact)
                _reset_process_caches()
                loader_calls = {"learning_first": 0, "strict": 0}
                learning = _measure_learning_first(run_dir, artifact, loader_calls)
                strict_walls = _measure_strict(run_dir, loader_calls)
                return _receipt(learning, strict_walls, loader_calls)


def main() -> int:
    if not mx.metal.is_available():
        raise SystemExit("#1566 witness requires Apple Metal")
    root = Path.cwd().resolve()
    source = (root / "vendor/legacy-v16").resolve()
    artifact = _artifact(root)
    if not source.is_dir():
        raise SystemExit("#1566 witness requires vendor/legacy-v16")
    previous = mx.default_device()
    mx.set_default_device(mx.gpu)
    try:
        receipt = _run_witness(root, source, artifact)
        print(
            "ISSUE1566_STRICT_MODE_BOUNDARY " + json.dumps(receipt, sort_keys=True),
            flush=True,
        )
        return 0
    finally:
        mx.set_default_device(previous)


if __name__ == "__main__":
    raise SystemExit(main())
