"""Matched disposable source-owned C16/C05 trial, never publishes a student."""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ARTIFACT = (
    "bilqis_mlx/bootstrap_assets/atlas/"
    "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7"
)
CAPABILITY = "B.AND"
PREFIX = "ISSUE1616_TRAINING "
MEMORY_CAP = 32 * 1024**3


def _timed_step(original, accepted_cache, preparation, times, label, horizon):
    import mlx.core as mx

    def timed(*args, **kwargs):
        kwargs.update(accepted_cache=accepted_cache, learning_first_cache=preparation)
        mx.synchronize()
        before = time.perf_counter()
        step = original(*args, **kwargs)
        mx.synchronize()
        times.append(time.perf_counter() - before)
        print(f"{label} step {len(times)}/{horizon}: {times[-1]:.3f}s", flush=True)
        return step
    return timed


def _optimizer_receipt(steps, rows, horizon):
    import numpy as np
    from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import retained_digest

    tx = steps[-1].transaction
    if len(rows) != 32 or tx.update_steps != horizon:
        raise RuntimeError("logical rows or optimizer horizon drift")
    participation = hashlib.sha256()
    for name, value in sorted(tx.optimizer.update_counts.items()):
        participation.update(name.encode())
        participation.update(np.asarray(value).tobytes())
    return {
        "optimizer_state_sha256": retained_digest(tx),
        "optimizer_participation_sha256": participation.hexdigest(),
        "training_source_coordinates": tx.training_source_coordinates,
        "optimizer_steps": tx.update_steps,
    }


def _attempt(c16, p, owner, timed, label, horizon, run_dir, parent, context,
             feature_path, artifact, accepted_cache):
    import mlx.core as mx
    from bilqis_mlx.learning.atlas_retention_decision import issue_factory_retention_decision
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode

    mx.clear_cache()
    mx.reset_peak_memory()
    mx.synchronize()
    attempt = time.perf_counter()
    with evidence_mode(strict=False), patch.object(c16, "train_bamf_factory_step", timed):
        with owner.install() if label == "compiled" else nullcontext():
            bound, rows, steps = c16.real_candidate_training_horizon(
                run_dir, parent, context, feature_path, artifact,
                learning_rate=p.C05_TRAINING_LEARNING_RATE, horizon=horizon,
                capability=CAPABILITY, source_each=32)
        mx.synchronize()
        training_wall = time.perf_counter() - attempt
        observed = []
        evaluation = p.evaluate_factory_retention_candidate(
            context, steps[-1].transaction, str(artifact), CAPABILITY,
            run_dir=run_dir, observer=observed.append,
            accepted_parent=parent, execution_cache=accepted_cache)
        issued = issue_factory_retention_decision(evaluation)
        mx.synchronize()
    wall = time.perf_counter() - attempt
    return bound, rows, steps, evaluation, issued, observed, training_wall, wall


def _arm(label, horizon):
    import mlx.core as mx

    from bilqis_mlx.runtime.factory_training_bridge import LearningFirstPreparationCache
    from bilqis_mlx.runtime.microbatch.compiled_route import compiled_route_cache_stats
    from bilqis_mlx.runtime.mlx_memory import training_memory_policy
    from bilqis_mlx.runtime.tests.capability.factory.owner import bamf_c16_2c_witness_support as c16
    from bilqis_mlx.runtime.tests.capability.factory.retention import retention_throughput_profile as p
    from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import retained_digest
    from scripts.bamf.profiling.issue1616.backbone import CompiledGroups

    root = Path.cwd()
    artifact = (root / ARTIFACT).resolve()
    source = (root / "vendor/legacy-v16").resolve()
    if not mx.metal.is_available() or not artifact.is_dir() or not source.is_dir():
        raise RuntimeError("native MLX and checked-in source fixtures required")
    mx.set_default_device(mx.gpu)
    mx.set_memory_limit(MEMORY_CAP)
    mx.set_cache_limit(0)
    with tempfile.TemporaryDirectory(prefix="issue1616-") as tmp, p.host_source_authority_patch():
        stage = Path(tmp)
        with patch.dict(os.environ, {
            "BILQIS_A01_ATLAS_BUNDLE": str(artifact),
            "BILQIS_ATLAS_REAL_ARTIFACT": str(artifact),
            "BILQIS_DATA_PLANE": str(stage / "plane.sqlite3"),
        }), training_memory_policy(mx):
            started = time.perf_counter()
            run_dir, _, _ = p._prepare_run(stage, root, source, artifact)
            parent, context, _, feature_path = p._execution_context(run_dir)
            accepted_cache = p.bind_accepted_execution_cache(run_dir)
            protection = p.bind_current_retention_protection_plan(context, parent, accepted_cache)
            cached_rows = p.bind_current_retention_source_rows(context, accepted_cache, CAPABILITY)
            initial = retained_digest(parent.retained_state)
            owner = CompiledGroups(context.release.release_sha256)
            preparation = LearningFirstPreparationCache()
            original = c16.train_bamf_factory_step
            times = []

            timed = _timed_step(original, accepted_cache, preparation, times, label, horizon)

            setup = time.perf_counter() - started
            print(f"{label} setup {setup:.3f}s; parent={initial}", flush=True)
            if horizon == 0:
                return {"label": label, "preflight": True, "parent_sha256": initial}
            bound, rows, steps, evaluation, issued, observed, training_wall, wall = _attempt(
                c16, p, owner, timed, label, horizon, run_dir, parent, context,
                feature_path, artifact, accepted_cache)
            peak = int(mx.get_peak_memory())
            cache_receipt = evaluation.parent_assessment_cache
            return {
                "label": label, "source_release": context.release.release_sha256,
                "source_seed": c16.SOURCE_SEED, "artifact": artifact.name,
                "parent_sha256": initial, "visit": bound.identity.to_record(),
                "training_rows": [row["id"] for row in rows],
                "protection_plan": protection.digest,
                "retention_capabilities": [item[0] for item in cached_rows],
                "parent_assessment_identity": (
                    cache_receipt.identity_sha256 if cache_receipt else None),
                "parent_assessment_sha256": (
                    cache_receipt.assessment_sha256 if cache_receipt else None),
                **_optimizer_receipt(steps, rows, horizon),
                "setup_wall_seconds": setup, "training_wall_seconds": training_wall,
                "attempt_wall_seconds": wall, "step_wall_seconds": times,
                "attempted_steps_per_minute": 60 * horizon / wall,
                "completed_component_trials_per_hour": 3600 / wall,
                "accepted": bool(issued.accepted),
                "decision_status": evaluation.decision.status.value,
                "decision_reason": evaluation.decision.reason,
                "outcome_scores": [list(row) for row in evaluation.decision.outcome_scores],
                "fixed_independent_competence_change_per_hour": "NOT_MEASURED",
                "retention_observations": observed,
                "peak_mlx_bytes": peak, "memory_cap_bytes": MEMORY_CAP,
                "backbone_compile": owner.stats(),
                "route_compile": compiled_route_cache_stats(),
                "samples": [dict(step.realized_cost) for step in steps],
            }


def _run(label, horizon):
    env = dict(os.environ, BILQIS_TEST_WORKERS="1", BILQIS_MLX_COMPILE_STABLE_KERNEL="1")
    command = [sys.executable, "-B", "-m", __name__ if __name__ != "__main__"
               else "scripts.bamf.profiling.issue1616.training",
               "--arm", label, "--horizon", str(horizon)]
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, bufsize=1)
    result = None
    try:
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            if line.startswith(PREFIX):
                if result is not None:
                    raise RuntimeError("duplicate arm receipt")
                result = json.loads(line[len(PREFIX):])
        if process.wait() or result is None:
            raise RuntimeError(f"{label} failed or emitted no receipt")
        return result
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=("stock", "compiled"))
    parser.add_argument("--horizon", type=int, default=12)
    args = parser.parse_args()
    if args.horizon not in (0, 12):
        parser.error("only preflight (0) or the predeclared 12-step horizon")
    if args.arm:
        print(PREFIX + json.dumps(_arm(args.arm, args.horizon), sort_keys=True), flush=True)
        return
    stock = _run("stock", args.horizon)
    compiled = _run("compiled", args.horizon)
    if not args.horizon:
        return
    keys = ("source_release", "source_seed", "artifact", "parent_sha256",
            "training_rows", "protection_plan", "training_source_coordinates",
            "optimizer_state_sha256", "optimizer_participation_sha256",
            "optimizer_steps", "accepted", "decision_status", "decision_reason",
            "outcome_scores")
    parity = {key: stock[key] == compiled[key] for key in keys}
    losses = [[s.get("loss_total") for s in arm["samples"]]
              for arm in (stock, compiled)]
    loss_observed = all(value is not None for arm in losses for value in arm)
    if loss_observed:
        parity["loss_sequence"] = losses[0] == losses[1]
    cache = compiled["backbone_compile"]
    summary = {
        "schema": "bilqis.issue1616.matched-component/v1",
        "parity": parity,
        "loss_sequence_observation": "MEASURED" if loss_observed else "NOT_MEASURED",
        "warm_step_wall_ratio": statistics.median(compiled["step_wall_seconds"][1:])
        / statistics.median(stock["step_wall_seconds"][1:]),
        "attempt_wall_ratio": compiled["attempt_wall_seconds"] / stock["attempt_wall_seconds"],
        "peak_memory_ratio": compiled["peak_mlx_bytes"] / stock["peak_mlx_bytes"],
        "observed_forward_graph_reuse": cache["python_graph_traces"] < cache["hits"] + cache["misses"],
        "fixed_independent_competence_change_per_hour": "NOT_MEASURED",
        "authorizing": False,
    }
    print("ISSUE1616_MATCHED " + json.dumps(summary, sort_keys=True), flush=True)
    if not all(parity.values()):
        raise SystemExit("matched trial numerical or source/decision parity failed")


if __name__ == "__main__":
    main()
