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
from contextlib import ExitStack, contextmanager
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mlx.core as mx

from bilqis_mlx.runtime.teacher_observation_capture import ObservationCapture
from bilqis_mlx.runtime.bamf_operator.session import (
    _SessionExecutionContext, prepare_bamf_visit,
)
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.bamf_operator.session_parts.session_support import _execution_context
from bilqis_mlx.runtime.mlx_memory import training_memory_policy
from bilqis_mlx.runtime.priority_planning_owner import PriorityPlanningCache
from bilqis_mlx.runtime.tests.capability.factory.retention import (
    retention_throughput_profile as profile,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.teacher_custody_fixtures import (
    adaptation as fixture_adaptation,
    selection_teacher,
)


SCHEMA = "bilqis.bamf.issue1566-strict-mode-boundary-witness/v1"
ROWS = 32
FULL_VISIT_HORIZON = 1
THROUGHPUT_HORIZON = 4


class _Observer:
    def __init__(self):
        self.values = {}

    def bind_parent(self, _parent):
        return None

    def update(self, **kwargs):
        self.values.update(kwargs)


@contextmanager
def _planning_timing(spans: dict[str, float]):
    from bilqis_mlx.runtime import active_grade_cadence
    from bilqis_mlx.runtime import lawful_teaching_frontier
    from bilqis_mlx.runtime import priority_authority

    targets = (
        (priority_authority, "bind_priority_planning_generation"),
        (priority_authority, "_require_planning_generation_identity"),
        (priority_authority, "_build_priority_planning_epoch"),
        (priority_authority, "_priority_planning_from_epoch"),
        (priority_authority, "_rejection_recency"),
        (priority_authority, "_priority_offers"),
        (lawful_teaching_frontier, "_issue_lawful_teaching_frontier_from_epoch"),
        (active_grade_cadence, "issue_active_grade_cadence"),
    )
    with ExitStack() as stack:
        for owner, name in targets:
            original = getattr(owner, name)

            def timed(*args, _name=name, _original=original, **kwargs):
                started = time.perf_counter()
                try:
                    return _original(*args, **kwargs)
                finally:
                    spans[_name] = spans.get(_name, 0.0) + max(
                        0.0, time.perf_counter() - started)

            stack.enter_context(patch.object(owner, name, timed))
        yield


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


def _prepared_sample(run_dir: Path, ordinary, planning_cache):
    observer = _Observer()
    planning_spans = {}
    visit_started = time.perf_counter()
    with _planning_timing(planning_spans):
        prepared = prepare_bamf_visit(
            run_dir,
            steps_per_visit=FULL_VISIT_HORIZON,
            batch_size=ROWS,
            reserve_gib=0.0,
            source_prefetch_workers=0,
            observer=observer,
            planning_cache=planning_cache,
            execution_context=ordinary,
        )
    mx.synchronize()
    steps = tuple(prepared.steps) or ((prepared.step,) if prepared.step is not None else ())
    step = steps[-1] if steps else None
    visit_wall = max(0.0, time.perf_counter() - visit_started)
    return {
        "prepared": prepared,
        "step": step,
        "steps": steps,
        "observer": observer.values,
        "planning_spans": planning_spans,
        "visit_wall": visit_wall,
        "planning_cache": planning_cache.metrics(),
    }


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
        mx.clear_cache()
        mx.reset_peak_memory()
        planning_cache = PriorityPlanningCache(run_dir)
        cold_visit = _prepared_sample(run_dir, ordinary, planning_cache)
        warm_visit = _prepared_sample(run_dir, ordinary, planning_cache)
    return {
        "cold_visit": cold_visit,
        "warm_visit": warm_visit,
        "accepted_state_metrics": accepted_state_metrics,
        "first_wall": first_wall,
        "second_wall": second_wall,
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


def _measure_candidate_horizon(
        stage: Path, root: Path, source: Path, artifact: Path) -> dict:
    run_dir, _parent, _context = profile._prepare_run(stage, root, source, artifact)
    _reset_process_caches()
    accepted_metrics = {}
    parent, source_context, _atlas_path, feature_path = _execution_context(
        run_dir, performance_metrics=accepted_metrics)
    mx.clear_cache()
    mx.reset_peak_memory()
    started = time.perf_counter()
    with evidence_mode(strict=False), patch.dict(os.environ, {
        "BILQIS_C05_PROFILE_CANDIDATE_HORIZON": str(THROUGHPUT_HORIZON),
    }):
        _bound, rows, step = profile._train_candidate(
            run_dir, parent, source_context, feature_path, artifact,
            "A.EDGE", ROWS)
    wall = max(0.0, time.perf_counter() - started)
    updates = int(step.transaction.update_steps)
    return {
        "capability": "A.EDGE",
        "logical_rows": len(rows),
        "candidate_horizon": THROUGHPUT_HORIZON,
        "optimizer_updates": updates,
        "training_wall_seconds": wall,
        "steps_per_minute": 0.0 if wall <= 0.0 else updates * 60.0 / wall,
        "last_step_realized_cost": dict(step.realized_cost),
        "accepted_state_metrics": accepted_metrics,
    }


def _receipt(learning, candidate_horizon, strict_walls, loader_calls: dict) -> dict:
    def sample_payload(sample):
        step = sample["step"]
        cost = {} if step is None else dict(step.realized_cost)
        steps = sample["steps"]
        candidate_step_walls = [
            float(dict(item.realized_cost).get("candidate_step_wall_seconds", 0.0))
            for item in steps
        ]
        observation = dict(sample["observer"])
        prepared = sample["prepared"]
        return {
            "prepared_status": prepared.status,
            "capability": prepared.capability,
            "full_prepared_visit_wall_seconds": sample["visit_wall"],
            "candidate_steps": len(steps),
            "steps_per_minute": (
                0.0 if sample["visit_wall"] <= 0.0
                else len(steps) * 60.0 / sample["visit_wall"]),
            "planning_wall_seconds": observation.get("planning_wall_seconds"),
            "planning_subspans": sample["planning_spans"],
            "planning_cache": sample["planning_cache"],
            "planning_offer_fanout_wall_seconds": observation.get(
                "planning_offer_fanout_wall_seconds"),
            "source_materialization_wall_seconds": observation.get(
                "source_materialization_wall_seconds"),
            "candidate_step_wall_seconds": cost.get("candidate_step_wall_seconds"),
            "candidate_steps_wall_seconds": candidate_step_walls,
            "candidate_steps_total_wall_seconds": sum(candidate_step_walls),
            "retention_wall_seconds": observation.get("retention_wall_seconds"),
            "optimizer_updates": (
                None if step is None else step.transaction.update_steps),
            "visit_observation": observation,
        }

    cold = sample_payload(learning["cold_visit"])
    warm = sample_payload(learning["warm_visit"])
    return {
        "schema": SCHEMA,
        "authorizing": False,
        "published": False,
        "human_run_mutated": False,
        "prepared_status": cold["prepared_status"],
        "capability": cold["capability"],
        "logical_rows": ROWS,
        "candidate_horizon": FULL_VISIT_HORIZON,
        "four_step_candidate_throughput": candidate_horizon,
        "learning_first": {
            "accepted_session_loader_calls": loader_calls["learning_first"],
            "cold_session_setup_wall_seconds": learning["first_wall"],
            "same_generation_reuse_wall_seconds": learning["second_wall"],
            "accepted_state_metrics": learning["accepted_state_metrics"],
            "cold_visit": cold,
            "warm_same_generation_visit": warm,
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
    bootstrap = SimpleNamespace(
        legacy_receipt={"teacher": selection_teacher()},
        adaptation=fixture_adaptation(),
        prior_region="issue1566-disposable-prior-region",
    )
    with training_memory_policy(mx):
        with profile.host_source_authority_patch(), \
                patch.object(ObservationCapture, "delivery", compatible_delivery), patch(
                    "bilqis_mlx.runtime.foundation_teacher_owner."
                    "foundation_teacher_bootstrap", return_value=bootstrap):
            with tempfile.TemporaryDirectory() as directory:
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
            with tempfile.TemporaryDirectory() as candidate_directory:
                candidate_stage = Path(candidate_directory)
                with patch.dict(os.environ, {
                    "BILQIS_A01_ATLAS_BUNDLE": str(artifact),
                    "BILQIS_ATLAS_REAL_ARTIFACT": str(artifact),
                    "BILQIS_DATA_PLANE": str(candidate_stage / "plane.sqlite3"),
                }):
                    candidate_horizon = _measure_candidate_horizon(
                        candidate_stage, root, source, artifact)
            return _receipt(
                learning, candidate_horizon, strict_walls, loader_calls)


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
