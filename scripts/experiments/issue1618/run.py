"""Matched FULL vs experimental FAST-mask native C16/C05 trials.

Run each arm in a fresh process with temporary learner and data-plane custody.
No production policy transition, activation cache or publication is exercised.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import importlib
import json
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.factory_training_bridge import LearningFirstPreparationCache
from bilqis_mlx.runtime.mlx_memory import training_memory_policy
from bilqis_mlx.learning.atlas_retention_decision import issue_factory_retention_decision
from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import retained_digest
from scripts.bamf.profiling import issue1578_logical_arm as fixture
from scripts.experiments.issue1618.fixed_probe import fixed_probe, prepare_probe
from scripts.experiments.issue1618.participation import selected_inputs, verify_optimizer

ARTIFACT = "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7"


def run(mode, batch_size, horizon):
    root = Path.cwd()
    artifact = root / "bilqis_mlx/bootstrap_assets/atlas" / ARTIFACT
    source = root / "vendor/legacy-v16"
    profile, c16 = fixture.profile, fixture.c16
    execution = importlib.import_module("bilqis_mlx.runtime.candidate.execution")
    calls = []

    def selection(parent):
        selected, active = selected_inputs(parent, mode)
        calls.append(selected)
        return selected, active

    with tempfile.TemporaryDirectory(prefix="issue1618-") as directory, \
            profile.host_source_authority_patch(), training_memory_policy(mx):
        stage = Path(directory)
        os.environ.update(BILQIS_A01_ATLAS_BUNDLE=str(artifact),
                          BILQIS_ATLAS_REAL_ARTIFACT=str(artifact),
                          BILQIS_DATA_PLANE=str(stage / "plane.sqlite3"))
        run_dir, parent, context = profile._prepare_run(stage, root, source, artifact)
        parent, context, _, feature_path = profile._execution_context(run_dir)
        cache = profile.bind_accepted_execution_cache(run_dir)
        protection = profile.bind_current_retention_protection_plan(context, parent, cache)
        profile.bind_current_retention_source_rows(context, cache, "B.AND")
        initial_digest = retained_digest(parent.retained_state)
        preparation = LearningFirstPreparationCache()
        original_train = c16.train_bamf_factory_step

        def train(*args, **kwargs):
            kwargs.update(learning_first_cache=preparation, accepted_cache=cache)
            return original_train(*args, **kwargs)

        print("ISSUE1618_SETUP", mode, initial_digest, flush=True)
        with evidence_mode(strict=False):
            expected_rows = context.draw_rows(seed=c16.SOURCE_SEED, capability="B.AND", each=batch_size)
            prepared = prepare_probe(context, parent, artifact, cache, expected_rows)
        print("ISSUE1618_PROBE_PREFLIGHT", mode, prepared.capabilities, prepared.parent_scores, flush=True)
        observed = []
        mx.clear_cache()
        mx.reset_peak_memory()
        started = time.perf_counter()
        with evidence_mode(strict=False), patch.object(execution, "derive_participation_inputs", selection), \
                patch.object(c16, "train_bamf_factory_step", side_effect=train):
            bound, rows, steps = c16.real_candidate_training_horizon(
                run_dir, parent, context, feature_path, artifact,
                learning_rate=profile.C05_TRAINING_LEARNING_RATE,
                horizon=horizon, capability="B.AND", source_each=batch_size)
            mx.synchronize()
            training_wall = time.perf_counter() - started
            transaction = steps[-1].transaction
            evaluation = profile.evaluate_factory_retention_candidate(
                context, transaction, str(artifact), "B.AND", run_dir=run_dir,
                observer=observed.append, accepted_parent=parent, execution_cache=cache)
            issued = issue_factory_retention_decision(evaluation)
            mx.synchronize()
            attempt_wall = time.perf_counter() - started
            peak = int(mx.get_peak_memory())
            print("ISSUE1618_C05", mode, evaluation.decision.reason, flush=True)
            assert len(calls) == horizon, f"intervention count {len(calls)} != {horizon}"
            assert all(item == calls[0] for item in calls)
            optimizer = verify_optimizer(parent, transaction, calls[0])
            assert retained_digest(parent.retained_state) == initial_digest
            assert tuple(row["id"] for row in rows) == tuple(row["id"] for row in expected_rows)
            proof = fixed_probe(context, parent, transaction, artifact, cache, rows, prepared)
        accepted = bool(issued.accepted)
        before, after = proof["parent_scores"], proof["candidate_scores"]
        retained = after if accepted else before
        proof["retention_selected_scores"] = retained
        proof["candidate_change_per_hour"] = {cap: (after[cap][0] - score[0]) * 3600 / attempt_wall
                                               for cap, score in before.items()}
        proof["retention_selected_change_per_hour"] = {
            cap: (retained[cap][0] - score[0]) * 3600 / attempt_wall for cap, score in before.items()}
        return {"mode": mode, "scope": "disposable genesis mask intervention; no publication",
                "actual_parent_policy": parent.retained_state.policy.mode,
                "initial_state_sha256": initial_digest,
                "candidate_state_sha256": retained_digest(transaction),
                "source_release_sha256": context.release.release_sha256,
                "atlas_artifact": ARTIFACT, "topology_sha256": parent.topology.digest,
                "extents_sha256": parent.extents.digest,
                "protection_plan_sha256": protection.digest,
                "source_seed": c16.SOURCE_SEED, "optimizer_step_seeds": list(range(17, 17 + horizon)),
                "optimizer": asdict(profile.HP), "learning_rate": profile.C05_TRAINING_LEARNING_RATE,
                "selected_visit": bound.identity.to_record(),
                "training_row_ids": [row["id"] for row in rows],
                "training_source_coordinates": transaction.training_source_coordinates,
                "logical_batch_size": batch_size, "attempted_steps": transaction.update_steps,
                "training_seconds": training_wall, "attempt_seconds": attempt_wall,
                "attempted_steps_per_minute": horizon * 60 / attempt_wall,
                "training_steps_per_minute": horizon * 60 / training_wall,
                "completed_candidate_trials_per_hour": 3600 / attempt_wall,
                "peak_mlx_bytes": peak,
                "gradient_launches": sum(int(s.realized_cost.get("c08_gradient_launches", 0)) for s in steps),
                "retention_accepted": accepted, "retention_reason": evaluation.decision.reason,
                "retention_outcome_scores": evaluation.decision.outcome_scores,
                "retention_evidence_sha256": evaluation.decision.evidence_sha256,
                "optimizer_proof": optimizer, "fixed_probe": proof,
                "activation_cache": "not used in native arm"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("FULL", "FAST"), required=True)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--horizon", type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.horizon <= 12 or not 2 <= args.batch_size <= 32:
        parser.error("disposable bounds: horizon 1..12; batch size 2..32")
    mx.set_default_device(mx.gpu)
    result = run(args.mode, args.batch_size, args.horizon)
    print("ISSUE1618_RESULT " + json.dumps(result, sort_keys=True, default=str), flush=True)


if __name__ == "__main__":
    main()
