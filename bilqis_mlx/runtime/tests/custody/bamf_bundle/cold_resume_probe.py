"""Clean-process cold-resume probe used by the B13.2 continuation witness.

The probe owns no production authority. It loads the published accepted
generation through the production custody path, executes the next optimizer
step through the production participation binder, measures the retention
evidence, asks the retention decision owner to decide, and publishes the
successor generation through the production admission path. The parent test
compares the cold-resumed successor with an uninterrupted continuation.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import mlx.core as mx
import numpy as np

from bilqis_mlx.learning.atlas_candidate import resolve_candidate
from bilqis_mlx.learning.atlas_retention_decision import decide_candidate_retention
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters
from bilqis_mlx.runtime.bamf_bundle.admission import (
    accept_and_publish, admit_candidate_step, derive_successor_bundle,
    load_accepted_generation,
)
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2

from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch

# The probe target sits below the published parameters so the first retained
# step, with the retained optimizer moments, reduces the measured probe loss.
PROBE_DIRECTION = -0.25
LEARNING_RATE = .001


def retained_digest(retained) -> str:
    """Deterministic digest of the reconstructed neural and optimizer state."""
    digest = hashlib.sha256()
    optimizer = retained.optimizer
    for group in ("parameters", "m", "v"):
        for name, value in sorted(getattr(optimizer, group).items()):
            digest.update(name.encode("utf-8"))
            digest.update(np.asarray(value, dtype=np.float32).tobytes())
    for name, value in sorted(optimizer.update_counts.items()):
        digest.update(name.encode("utf-8"))
        digest.update(np.asarray(value).tobytes())
    return digest.hexdigest()


def probe_target(parameters) -> dict:
    """One deterministic probe target per published parameter."""
    return {name: mx.array(value) + PROBE_DIRECTION
            for name, value in parameters.items()}


def probe_loss(parameters, target) -> float:
    """Measured probe loss of the candidate state against the probe target."""
    total = 0.0
    for name, value in parameters.items():
        difference = np.asarray(value, dtype=np.float32) - np.asarray(
            target[name], dtype=np.float32)
        total += float(np.square(difference).sum())
    return total


def probe_gradients(parameters, target) -> dict:
    """Gradient of the measured probe loss against the published parameters."""
    return {name: 2.0 * (mx.array(value) - mx.array(target[name]))
            for name, value in parameters.items()}


def continue_generation(run) -> dict:
    """Continue the published generation once and publish the successor.

    The same function serves the uninterrupted continuation and the clean
    process cold resume, so both run identical production semantics.
    """
    run = Path(run)
    pointer_path = run / "bamf-state.json"
    pointer = json.loads(pointer_path.read_text())
    with shape_patch():
        student = load_accepted_generation(run)
        resumed = {
            "generation": student.generation,
            "manifest_sha256": pointer["manifest_sha256"],
            "state_digest": retained_digest(student.retained_state),
            "teacher_state": dict(student.teacher_state),
            "optimizer_step": student.retained_state.optimizer_step,
        }
        names = tuple(sorted(student.retained_state.optimizer.parameters))
        parameters = student.retained_state.optimizer.parameters
        target = probe_target(parameters)
        loss_before = probe_loss(parameters, target)
        transaction = admit_candidate_step(
            run, probe_gradients(parameters, target),
            motif_reads=(), loss_bearing_target=True,
            teacher_hparams=AdamWHyperparameters(
                LEARNING_RATE, (.9, .95), 1e-8, .01),
            decay={name: True for name in names}, max_norm=1.)
        accepted = resolve_candidate(transaction, accepted=True)
        loss_after = probe_loss(accepted.optimizer.parameters, target)
        gain = loss_before - loss_after
        decision = decide_candidate_retention(
            no_target_gain=not gain > 0.0, same_grade_net_gain=1 if gain > 0.0 else 0,
            fixed_grade_regression=False, active_grade_regression=False,
            whole_school_regression=False, frontier_measured=True,
            fragile_losses=0, exceeded=False)
        if not decision.accepted:
            raise ValueError(
                f"COLD_RESUME_CONTINUATION_REJECTED before={loss_before} after={loss_after}")
        bundle = derive_successor_bundle(
            student, accepted,
            parent_manifest_sha256=pointer["manifest_sha256"],
            delivery_events=({
                "event": "BAMF_GENERATION_ACCEPTED",
                "optimizer_step": accepted.optimizer_step},))
        published = accept_and_publish(
            run, bundle, accepted, decision=decision,
            feature_sha256=student.extents.factor_map_digest)
    resumed["published"] = published
    resumed["decision"] = decision.to_record()
    resumed["probe_loss_before"] = loss_before
    resumed["probe_loss_after"] = loss_after
    resumed["successor_optimizer_step"] = accepted.optimizer_step
    resumed["successor_digest"] = retained_digest(accepted)
    resumed["successor_update_counts"] = {
        name: np.asarray(value).tolist()
        for name, value in sorted(accepted.optimizer.update_counts.items())}
    resumed["successor_proof_digests"] = [
        proof.digest for proof in accepted.step_proofs]
    return resumed


def main(argv) -> int:
    print(json.dumps(continue_generation(argv[1])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
