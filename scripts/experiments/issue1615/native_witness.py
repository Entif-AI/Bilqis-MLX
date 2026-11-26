#!/usr/bin/env python3
"""Disposable production B11/C08 candidate-step A/B with an isolated trie group kernel.

Only ordinary, motif-free, source-owned traces are eligible. Frame closures and
every descendant are row-private. B05, adapters, typed readout, loss, participation,
optimizer and publication boundaries remain the production implementation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import mlx.core as mx
import numpy as np

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.mlx_memory import training_memory_policy
from bilqis_mlx.runtime.tests.capability.factory.retention import retention_throughput_profile as fixture
from bilqis_mlx.runtime.tests.model.execution.test_atlas_model_microbatch import FP32_ATOL, FP32_RTOL
from bilqis_mlx.runtime.teacher_observation_capture import ObservationCapture


from intervention import instrument
import assessment
from bilqis_mlx.runtime.factory_training_bridge import LearningFirstPreparationCache
from bilqis_mlx.runtime.tests.capability.factory.owner import bamf_c16_2c_witness_support as c16


def compare_tree(a, b, *, exact=False):
    if set(a) != set(b):
        raise AssertionError("parameter leaf mismatch")
    maximum = {}
    failures = []
    for key in a:
        x, y = np.asarray(a[key]), np.asarray(b[key])
        if x.shape != y.shape or x.dtype != y.dtype:
            raise AssertionError(f"shape/dtype drift: {key}")
        if exact:
            same = np.array_equal(x, y)
            maximum[key] = 0 if same else 1
        else:
            same = np.allclose(x, y, atol=FP32_ATOL, rtol=FP32_RTOL)
            maximum[key] = float(np.max(np.abs(x-y)))
        if not same:
            failures.append(key)
    return {"max_absolute_error_by_leaf": maximum, "failed_leaves": failures}


def run_arm(stage, artifact, mode, args, *, capture_gradients):
    stage.mkdir()
    counts, captures = Counter(), []
    with patch.dict(os.environ, {
            "BILQIS_A01_ATLAS_BUNDLE": str(artifact),
            "BILQIS_ATLAS_REAL_ARTIFACT": str(artifact),
            "BILQIS_DATA_PLANE": str(stage / "plane.sqlite3"),
            "BILQIS_MLX_COMPILE_STABLE_KERNEL": "0",
    }):
        run_dir, parent, source_context = fixture._prepare_run(
            stage, ROOT, ROOT / "vendor/legacy-v16", artifact)
        parent, source_context, _, feature_path = fixture._execution_context(run_dir)
        initial_identity = candidate_identity_digest(parent.retained_state)
        original_delivery = ObservationCapture.delivery
        cache = fixture.bind_accepted_execution_cache(run_dir)
        preparation = LearningFirstPreparationCache()
        original_train = c16.train_bamf_factory_step

        def train(*args, **kwargs):
            kwargs.update(learning_first_cache=preparation, accepted_cache=cache)
            return original_train(*args, **kwargs)

        proof = None
        if args.assess:
            fixture.bind_current_retention_protection_plan(source_context, parent, cache)
            fixture.bind_current_retention_source_rows(source_context, cache, args.capability)
            with evidence_mode(strict=False):
                expected_rows = source_context.draw_rows(
                    seed=c16.SOURCE_SEED, capability=args.capability, each=args.rows)
                probe = assessment.prepare(source_context, parent, artifact, cache,
                                           args.capability, expected_rows)
            print("PROBE_READY", mode, probe.capabilities, probe.parent_scores, flush=True)

        def compatible_delivery(self, *args, fresh_support=(), **kwargs):
            if fresh_support:
                raise AssertionError("witness refuses nonempty fresh support")
            return original_delivery(self, *args, **kwargs)

        mx.clear_cache()
        mx.reset_peak_memory()
        baseline_bytes = int(mx.get_active_memory())
        with evidence_mode(strict=False), patch.object(
                ObservationCapture, "delivery", compatible_delivery), patch.object(
                c16, "train_bamf_factory_step", side_effect=train), instrument(
                mode, counts, captures, capture_gradients):
            started = time.perf_counter()
            bound, rows, steps = fixture.real_candidate_training_horizon(
                run_dir, parent, source_context, feature_path, artifact,
                learning_rate=fixture.C05_TRAINING_LEARNING_RATE,
                horizon=args.horizon, capability=args.capability, source_each=args.rows)
            mx.synchronize()
            wall = time.perf_counter() - started
        training_peak = int(mx.get_peak_memory())
        if args.assess:
            if tuple(row["id"] for row in rows) != tuple(row["id"] for row in expected_rows):
                raise AssertionError("Training row drift from preflight")
            with evidence_mode(strict=False):
                proof = assessment.finish(source_context, parent, steps[-1].transaction,
                                          artifact, cache, rows, probe, run_dir,
                                          args.capability, wall)
        if candidate_identity_digest(parent.retained_state) != initial_identity:
            raise AssertionError("Parent state mutated")
        if not counts["eligible_batches"] or not counts["vectorized_launches"]:
            raise AssertionError("no eligible production B11 batch observed")
        if mode != "control" and not counts["shared_groups"]:
            raise AssertionError("no shared group executed")
        optimizer = steps[-1].transaction.optimizer
        # Candidate remains disposable. No accepted learner publication.
        receipt = {"mode": mode, "counts": dict(counts), "wall_seconds": wall,
                   "initial_candidate_identity": initial_identity,
                   "baseline_mlx_bytes": baseline_bytes,
                   "peak_mlx_bytes": training_peak,
                   "incremental_peak_mlx_bytes": training_peak - baseline_bytes,
                   "teacher_trial": proof,
                   "rows": [row["id"] for row in rows],
                   "capability": args.capability, "horizon": args.horizon,
                   "attempted_steps_per_minute": args.horizon * 60 / wall,
                   "optimizer_step": steps[-1].transaction.parent.optimizer_step
                                     + steps[-1].transaction.update_steps,
                   "source_seed": 37116,
                   "microbatch_losses": [item["loss"] for item in captures],
                   "training_source_coordinates": steps[-1].transaction.training_source_coordinates}
        print("ARM " + json.dumps(receipt, sort_keys=True), flush=True)
        return receipt, optimizer, captures


def save_tree(directory, tree):
    directory.mkdir()
    for key, value in tree.items():
        np.save(directory / (key + ".npy"), np.asarray(value), allow_pickle=False)


def load_tree(directory):
    return {p.stem: np.load(p, mmap_mode="r", allow_pickle=False)
            for p in directory.glob("*.npy")}


def arm_process(stage, args):
    mx.set_default_device(mx.cpu if args.device == "cpu" else mx.gpu)
    artifact = ROOT / "bilqis_mlx/bootstrap_assets/atlas/5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7"
    with fixture.host_source_authority_patch(), training_memory_policy(mx):
        receipt, optimizer, captures = run_arm(stage / "run", artifact, args.arm, args,
                                               capture_gradients=not args.timing_only)
        for index, capture in enumerate(captures):
            save_tree(stage / ("gradients-" + str(index)), capture.pop("gradients"))
        for key in ("parameters", "m", "v", "update_counts"):
            save_tree(stage / key, getattr(optimizer, key))
        (stage / "result.json").write_text(json.dumps(
            {"receipt": receipt, "captures": captures}, sort_keys=True))


def compare_arms(stage, args):
    for arm in ("control", args.mode):
        destination = stage / arm
        destination.mkdir()
        command = [sys.executable, "-B", str(Path(__file__).resolve()),
                   "--device", args.device, "--capability", args.capability,
                   "--rows", str(args.rows), "--horizon", str(args.horizon),
                   "--mode", args.mode, "--arm", arm, "--output", str(destination)]
        if args.timing_only:
            command.append("--timing-only")
        if args.assess:
            command.append("--assess")
        subprocess.run(command, check=True, cwd=ROOT)
    control, trial = (json.loads((stage / arm / "result.json").read_text())
                      for arm in ("control", args.mode))
    a, b = control["receipt"], trial["receipt"]
    ag, bg = control["captures"], trial["captures"]
    matched = all(a[key] == b[key] for key in (
        "rows", "initial_candidate_identity", "optimizer_step",
        "source_seed", "training_source_coordinates", "horizon", "capability"))
    if not matched or len(ag) != len(bg):
        raise AssertionError("initial state, lesson, or optimizer coordinates drifted")
    gradients = []
    for index, (left, right) in enumerate(zip(ag, bg, strict=True)):
        path = "gradients-" + str(index)
        if args.timing_only:
            parity = None
        else:
            parity = compare_tree(load_tree(stage / "control" / path),
                                  load_tree(stage / args.mode / path))
        differing_fields = sorted({key for x, y in zip(
            left["participation"], right["participation"], strict=True)
            for key in x if x[key] != y[key]})
        differing_authority = sorted(key for key in left["authority"]
                                     if left["authority"][key] != right["authority"][key])
        gradients.append({
            "loss_close": bool(np.isclose(left["loss"], right["loss"],
                                          atol=FP32_ATOL, rtol=FP32_RTOL)),
            "losses": [left["loss"], right["loss"]],
            "participation_equal": not differing_fields and not differing_authority,
            "differing_participation_fields": differing_fields,
            "differing_authority_coordinates": differing_authority,
            "authority": [left["authority"], right["authority"]],
            "validated_local_tokens": [left["validated_local_token"],
                                       right["validated_local_token"]],
            "gradient_parity": parity})
    optimizer = {key: compare_tree(load_tree(stage / "control" / key),
                                   load_tree(stage / args.mode / key),
                                   exact=key == "update_counts")
                 for key in ("parameters", "m", "v", "update_counts")}
    assessment_parity = None
    if args.assess:
        x, y = a["teacher_trial"], b["teacher_trial"]
        p, q = x["fixed_probe"], y["fixed_probe"]
        assessment_parity = (all(p[key] == q[key] for key in (
            "seed", "capabilities", "row_ids", "cohort_sha256",
            "parent_scores", "candidate_scores", "retention_selected_scores"))
            and all(x[key] == y[key] for key in (
                "retention_accepted", "retention_reason", "retention_outcome_scores")))
    passed = (assessment_parity is not False and all(g["loss_close"] and g["participation_equal"]
                  and (g["gradient_parity"] is None
                       or not g["gradient_parity"]["failed_leaves"]) for g in gradients)
              and all(not t["failed_leaves"] for t in optimizer.values()))
    result = {"schema": "bilqis.bamf.issue1615-native-witness/v2",
              "device": args.device, "control": a, "trial": b,
              "matched_initial_state_and_lesson": matched,
              "assessment_parity": assessment_parity,
              "gradients": gradients, "optimizer": optimizer, "passed": passed,
              "fp32_atol": FP32_ATOL, "fp32_rtol": FP32_RTOL,
              "timing_only": args.timing_only,
              "speed_ratio": a["wall_seconds"] / b["wall_seconds"],
              "authorizing": False, "published": False}
    print("RESULT " + json.dumps(result, sort_keys=True), flush=True)
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cpu", "gpu"), default="cpu")
    parser.add_argument("--capability", default="B.AND")
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--horizon", type=int, default=1)
    parser.add_argument("--mode", choices=("dense", "gathered"), default="gathered")
    parser.add_argument("--assess", action="store_true", help="Complete C05 trial and held-out probe")
    parser.add_argument("--timing-only", action="store_true",
                        help="Do not retain raw gradients; compare losses, participation and optimizer")
    parser.add_argument("--arm", choices=("control", "dense", "gathered"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.arm:
        if args.output is None:
            parser.error("--arm requires --output")
        arm_process(args.output, args)
        return 0
    with tempfile.TemporaryDirectory(prefix="issue1615-matched-") as directory:
        return compare_arms(Path(directory), args)


if __name__ == "__main__":
    raise SystemExit(main())
