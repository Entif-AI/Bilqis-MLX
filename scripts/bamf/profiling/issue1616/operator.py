"""Supplementary matched ordinary operator trial with a pinned fixed exam.

Uses the read-only #1607 frozen-campaign donor. Both arms run current source
and identical operator settings; no production toggle or live student write.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch


DONOR_SHA = "e87bb2598c6a15657a328cae86f97c00f6b55af5c9136c728b5fc4a0e01446ed"
BASE_SCORE = 44
VISITS, HORIZON, BATCH = 2, 12, 32
MEMORY_CAP = 32 * 1024**3
ARMS = ("stock", "compiled")
from scripts.bamf.profiling.issue1616.operator_receipts import (
    compare, exam_overlap, outcomes,
)


def donor(path, output):
    if hashlib.sha256(path.read_bytes()).hexdigest() != DONOR_SHA:
        raise SystemExit("frozen campaign donor digest mismatch")
    spec = importlib.util.spec_from_file_location("issue1616_frozen_campaign", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = output
    return module


def observe_plan(original, owner, observations):
    def observe(*args, **kwargs):
        if kwargs["source_context"].release.release_sha256 != owner.release:
            raise RuntimeError("source release changed during matched arm")
        result = original(*args, **kwargs)
        gradient, _, _, tx, loss = result[:5]
        started = time.perf_counter()
        prepared = kwargs["prepared"].training_batch
        rows = [(row.provenance.source_family_id, row.provenance.episode_id)
                for row in prepared.rows]
        observations.append({
            "loss": float(loss), "rows": rows,
            "source_coordinates": tx.training_source_coordinates,
            "gradient_launches": getattr(gradient, "gradient_launches", None),
            "materialization_barriers": getattr(gradient, "materialization_barriers", None),
            "scalar_fallback_rows": getattr(gradient, "scalar_fallback_rows", None),
            "observation_seconds": time.perf_counter() - started,
        })
        return result
    return observe


def worker(args, h):
    import bilqis_mlx
    import mlx.core as mx
    from bilqis_mlx.runtime.bamf_operator import session
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
    from bilqis_mlx.runtime.bamf_operator.session_parts.session_support import _execution_context
    from bilqis_mlx.runtime.candidate import step
    from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import retained_digest
    from bilqis_mlx.presentation.operator_cli.bamf_resume_dispatch import _live_bamf_dashboard_refresh
    from scripts.bamf.profiling.issue1566_teacher_yield_witness import _seed_cadence_projection, _dashboard
    from scripts.bamf.profiling.issue1616.backbone import CompiledGroups

    folder = args.output / args.worker
    run, plane = folder / "run", folder / "plane.sqlite3"
    h.require(Path(bilqis_mlx.__file__).resolve().is_relative_to(Path.cwd().resolve()), "wrong source snapshot")
    h.require(Path(os.environ["BILQIS_DATA_PLANE"]).resolve() == plane.resolve(), "wrong plane")
    h.require(run.resolve() != (args.output.parent / "aspirant").resolve(), "sovereign run prohibited")
    mx.set_default_device(mx.gpu)
    mx.set_memory_limit(MEMORY_CAP)
    mx.set_cache_limit(0)
    _seed_cadence_projection(run, plane, h.projection())
    parent, context, _, _ = _execution_context(run)
    h.require(parent.generation == 51 and parent.retained_state.optimizer_step == 509, "initial learner drift")
    owner = CompiledGroups(context.release.release_sha256)
    initial = retained_digest(parent.retained_state)
    del parent, context
    board, draws = _dashboard(run)
    offset = (run / "events.jsonl").stat().st_size
    observations = []
    mx.clear_cache()
    mx.reset_peak_memory()
    mx.synchronize()
    print("OPERATOR_ARM_START", args.worker, owner.release, initial, flush=True)
    started = time.perf_counter()
    with patch.object(step, "_execute_candidate_plan",
                      observe_plan(step._execute_candidate_plan, owner, observations)):
        with owner.install() if args.worker == "compiled" else nullcontext():
            with _live_bamf_dashboard_refresh(board):
                result = session.operate_bamf(
                    run, minutes=5, max_visits=VISITS, steps_per_visit=HORIZON,
                    batch_size=BATCH, reserve_gib=100.0, source_prefetch_workers=2,
                    strict_mode=False, progress=lambda msg: print(args.worker, msg, flush=True))
            mx.synchronize()
    wall = time.perf_counter() - started
    peak = int(mx.get_peak_memory())
    attempts = outcomes(run, offset)
    attempted = sum(x["steps"] for x in attempts)
    report = {
        "label": args.worker, "wall_seconds": wall, "peak_mlx_bytes": peak,
        "initial_manifest": h.BASE_MANIFEST, "initial_optimizer_sha256": initial,
        "source_release": owner.release, "attempts": attempts, "attempted_steps": attempted,
        "attempted_steps_per_minute": attempted * 60 / wall,
        "completed_teacher_trials_per_hour": len(attempts) * 3600 / wall,
        "visits": result.visits, "accepted": result.accepted, "rejected": result.rejected,
        "generation": result.generation, "optimizer_step": result.optimizer_step,
        "status": str(result.status), "dashboard_draws": draws,
        "backbone_compile": owner.stats(), "steps": observations,
    }
    h.write(folder / "training.json", report)
    h.require(attempted == VISITS * HORIZON and len(attempts) == VISITS, "incomplete matched campaign")
    h.require(len(observations) == attempted, "missing numerical observations")
    print("OPERATOR_TRAINING_COMPLETE", args.worker, wall, attempted, owner.stats(), flush=True)
    mx.clear_cache()
    with evidence_mode(strict=True):
        report["exam"] = h.score(run)
        final, context, _, _ = _execution_context(run)
        report["final_optimizer_sha256"] = retained_digest(final.retained_state)
        h.require(context.release.release_sha256 == owner.release, "final source release drift")
        report["exam_overlap"] = exam_overlap(context, h, observations)
    report["exam_cohort_sha256"] = h.COHORT
    delta = report["exam"]["correct"] - BASE_SCORE
    report["fixed_exam_gain_correct_per_hour"] = delta * 3600 / wall
    report["fixed_exam_gain_pp_per_hour"] = delta * 100 / report["exam"]["total"] * 3600 / wall
    report["fixed_independent_competence_change_per_hour"] = (
        report["fixed_exam_gain_pp_per_hour"]
        if not any(report["exam_overlap"].values()) else "NOT_MEASURED")
    h.write(folder / "result.json", report)
    h.require(h.read(h.BASE / "bamf-state.json")["manifest_sha256"] == h.BASE_MANIFEST, "frozen source mutated")
    print("OPERATOR_ARM_COMPLETE", args.worker, report["exam"], report["exam_overlap"], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--donor", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--worker", choices=ARMS)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    args.output = args.output.resolve()
    h = donor(args.donor, args.output)
    if args.worker:
        worker(args, h)
        return
    h.preflight()
    if args.preflight:
        return
    for arm in ARMS:
        h.clone(arm)
    for arm in ARMS:
        env = dict(os.environ, PYTHONPATH=str(Path.cwd().resolve()),
                   BILQIS_DATA_PLANE=str(args.output / arm / "plane.sqlite3"),
                   BILQIS_MLX_COMPILE_STABLE_KERNEL="1", BILQIS_TEST_WORKERS="1")
        subprocess.run([sys.executable, "-B", "-m",
                        "scripts.bamf.profiling.issue1616.operator",
                        "--donor", str(args.donor), "--output", str(args.output),
                        "--worker", arm], env=env, check=True)
    result = compare(*(h.read(args.output / arm / "result.json") for arm in ARMS))
    h.write(args.output / "comparison.json", result)
    print("ISSUE1616_OPERATOR_COMPARISON", json.dumps(
        {k: v for k, v in result.items() if k not in ARMS}, sort_keys=True), flush=True)
    h.require(all(result["behavioral_parity"].values()), "operator behavioral outcome drift")


if __name__ == "__main__":
    main()
