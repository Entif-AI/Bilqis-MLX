#!/usr/bin/env python3
"""Run one disposable #1578 logical-batch learning-policy arm."""
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

from bilqis_mlx.learning.atlas_retention_decision import (
    issue_factory_retention_decision,
)
from bilqis_mlx.runtime.factory_training_bridge import LearningFirstPreparationCache
from bilqis_mlx.runtime.mlx_memory import training_memory_policy
from bilqis_mlx.runtime.teacher_observation_capture import ObservationCapture
import bilqis_mlx.runtime.tests.capability.factory.owner.bamf_c16_2c_witness_support as c16
from bilqis_mlx.runtime.tests.capability.factory.retention import (
    retention_throughput_profile as profile,
)


def _compatible_delivery(original):
    def delivery(self, *args, fresh_support=(), **kwargs):
        if fresh_support:
            raise AssertionError(
                "#1578 logical witness refuses non-empty fresh support"
            )
        return original(self, *args, **kwargs)

    return delivery


def _accepted_setup(run_dir, source_context, parent):
    metrics = {}
    parent, source_context, _atlas_path, feature_path = profile._execution_context(
        run_dir, performance_metrics=metrics
    )
    metrics["accepted_state_setup_wall_seconds"] = sum(
        float(metrics.get(name, 0.0))
        for name in (
            "accepted_runtime_host_wall_seconds",
            "accepted_generation_load_wall_seconds",
            "accepted_source_context_wall_seconds",
            "accepted_feature_authentication_wall_seconds",
        )
    )
    started = time.perf_counter()
    accepted_cache = profile.bind_accepted_execution_cache(run_dir)
    protection = profile.bind_current_retention_protection_plan(
        source_context, parent, accepted_cache
    )
    cached_rows = profile.bind_current_retention_source_rows(
        source_context, accepted_cache, "B.AND"
    )
    return (
        parent,
        source_context,
        feature_path,
        metrics,
        protection,
        cached_rows,
        max(0.0, time.perf_counter() - started),
    )


def _train(run_dir, parent, source_context, feature_path, artifact, batch_size, horizon):
    mx.clear_cache()
    mx.reset_peak_memory()
    started = time.perf_counter()
    bound, rows, steps = c16.real_candidate_training_horizon(
        run_dir,
        parent,
        source_context,
        feature_path,
        artifact,
        learning_rate=profile.C05_TRAINING_LEARNING_RATE,
        horizon=horizon,
        capability="B.AND",
        source_each=batch_size,
    )
    return bound, rows, steps, max(0.0, time.perf_counter() - started)


def _evaluate(run_dir, source_context, artifact, step, observed):
    started = time.perf_counter()
    evaluation = profile.evaluate_factory_retention_candidate(
        source_context,
        step.transaction,
        str(artifact),
        "B.AND",
        run_dir=run_dir,
        observer=observed.append,
    )
    mx.synchronize()
    return (
        evaluation,
        issue_factory_retention_decision(evaluation),
        max(0.0, time.perf_counter() - started),
    )


def _result(receipt, steps, rows, horizon, batch_size, attempt_wall):
    costs = tuple(dict(item.realized_cost) for item in steps)
    accepted = bool(receipt["accepted"])
    return {
        "logical_batch_size": batch_size,
        "optimizer_steps": horizon,
        "row_presentations": batch_size * horizon,
        "training_rows": len(rows),
        "gradient_launches_total": sum(
            int(cost.get("c08_gradient_launches", 0)) for cost in costs
        ),
        "rows_per_launch": costs[-1].get("c08_rows_per_gradient_launch"),
        "physical_microbatch_size": costs[-1].get("c08_microbatch_size"),
        "physical_microbatch_count": costs[-1].get("c08_microbatch_count"),
        "estimated_peak_bytes_max": max(
            int(cost.get("c08_estimated_peak_bytes", 0)) for cost in costs
        ),
        "actual_mlx_peak_bytes": int(mx.get_peak_memory()),
        "candidate_step_wall_seconds_total": sum(
            float(cost.get("candidate_step_wall_seconds", 0.0)) for cost in costs
        ),
        "c08_logical_batch_wall_seconds_total": sum(
            float(cost.get("c08_logical_batch_wall_seconds", 0.0)) for cost in costs
        ),
        "b11_autodiff_materialization_wall_seconds_total": sum(
            float(
                cost.get(
                    "b11_autodiff_materialization_wall_seconds",
                    0.0,
                )
            )
            for cost in costs
        ),
        "attempt_wall_seconds": receipt["attempt_wall_seconds"],
        "attempted_steps_per_hour": receipt["attempted_steps_per_hour"],
        "retained_steps_per_hour": receipt["retained_steps_per_hour"],
        "accepted": accepted,
        "retention_yield": 1.0 if accepted else 0.0,
        "retained_candidates_per_hour": (
            3600.0 / attempt_wall if accepted and attempt_wall > 0 else 0.0
        ),
        "steps_per_retention": horizon if accepted else None,
        "decision_status": receipt["decision_status"],
        "decision_reason": receipt["decision_reason"],
        "outcome_scores": receipt["outcome_scores"],
        "useful_retentions_per_hour": "NOT_MEASURED",
        "useful_retention_reason": (
            "Disposable C05 evaluation is not a published durable "
            "retention or downstream usefulness witness."
        ),
    }


def _run_arm(root, artifact, source, batch_size, horizon):
    cache = LearningFirstPreparationCache()
    original_train = c16.train_bamf_factory_step

    def train_with_cache(*args, **kwargs):
        kwargs["learning_first_cache"] = cache
        return original_train(*args, **kwargs)

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
        ):
            stage = Path(directory)
            os.environ["BILQIS_A01_ATLAS_BUNDLE"] = str(artifact)
            os.environ["BILQIS_ATLAS_REAL_ARTIFACT"] = str(artifact)
            os.environ["BILQIS_DATA_PLANE"] = str(stage / "plane.sqlite3")
            run_dir, parent, source_context = profile._prepare_run(
                stage, root, source, artifact
            )
            (
                parent,
                source_context,
                feature_path,
                accepted_metrics,
                protection,
                cached_rows,
                retention_setup_wall,
            ) = _accepted_setup(run_dir, source_context, parent)
            observed = []
            attempt_started = time.perf_counter()
            bound, rows, steps, training_wall = _train(
                run_dir,
                parent,
                source_context,
                feature_path,
                artifact,
                batch_size,
                horizon,
            )
            step = steps[-1]
            profile._print_preflight(
                "B.AND",
                batch_size,
                retention_setup_wall,
                protection,
                cached_rows,
                step,
                source_context,
                training_wall,
            )
            evaluation, issued, retention_wall = _evaluate(
                run_dir, source_context, artifact, step, observed
            )
            attempt_wall = max(0.0, time.perf_counter() - attempt_started)
            receipt = profile._profile_receipt(
                "B.AND",
                bound,
                rows,
                step,
                cached_rows,
                evaluation,
                issued,
                observed,
                training_wall,
                retention_setup_wall,
                retention_wall,
                attempt_wall,
                accepted_metrics,
            )
            return _result(receipt, steps, rows, horizon, batch_size, attempt_wall)


def main() -> int:
    root = Path.cwd()
    artifact = (root / os.environ["ISSUE1578_ARTIFACT_REL"]).resolve()
    source = (root / "vendor/legacy-v16").resolve()
    batch_size = int(os.environ["ISSUE1578_LOGICAL_BATCH_SIZE"])
    horizon = int(os.environ["ISSUE1578_HORIZON"])
    if not artifact.is_dir() or not source.is_dir():
        raise SystemExit(
            "#1578 witness requires checked-in Atlas and legacy source fixtures"
        )

    previous = mx.default_device()
    mx.set_default_device(mx.gpu)
    try:
        result = _run_arm(root, artifact, source, batch_size, horizon)
        print(
            "ISSUE1578_LOGICAL_RESULT " + json.dumps(result, sort_keys=True),
            flush=True,
        )
    finally:
        mx.set_default_device(previous)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
