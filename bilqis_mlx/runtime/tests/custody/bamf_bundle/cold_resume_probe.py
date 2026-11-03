"""Clean-process cold-resume probe used by the B13.2 continuation witness.

The probe owns no production authority. It loads the published accepted
generation through the production custody path, executes the next optimizer
step through the production participation binder, and publishes the successor
generation through the production admission path. The parent test compares the
reconstructed state with the in-process state.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import mlx.core as mx
import numpy as np

from bilqis_mlx.learning.atlas_candidate import resolve_candidate
from bilqis_mlx.learning.atlas_plasticity import GroupEligibility
from bilqis_mlx.learning.atlas_participation import ActiveAdmittedRows
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters
from bilqis_mlx.runtime.bamf_bundle.admission import (
    accept_and_publish, admit_candidate_step, derive_successor_bundle,
    load_accepted_generation,
)
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2

from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch


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


def next_visit_evidence(student):
    """Rebuild the next-visit execution evidence from the published custody."""
    identity_rows = tuple(sorted(
        (row.bank_index, row.row_index)
        for row in student.retained_state.policy.row_ages))
    names = tuple(sorted(student.retained_state.optimizer.parameters))
    return identity_rows, names


def main(argv) -> int:
    run = Path(argv[1])
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
        identity_rows, names = next_visit_evidence(student)
        eligibility = GroupEligibility(
            mode="FULL", eligible_parameter_names=names, frozen_parameter_names=(),
            admitted_identity_rows=identity_rows, fast_identity_rows=identity_rows,
            established_identity_rows=())
        active = ActiveAdmittedRows(identity_rows=identity_rows)
        transaction = admit_candidate_step(
            student, {name: mx.zeros_like(value) for name, value
                      in student.retained_state.optimizer.parameters.items()},
            motif_reads=(), executed_parameter_names=names,
            visible_identity_rows=identity_rows, feedback_identity_rows=(),
            local_slot_rows=(), loss_bearing_target=True,
            group_eligible=eligibility, active_admitted=active,
            spec=ModelTopologySpecV2(), extents=student.extents,
            teacher_hparams=AdamWHyperparameters(.001, (.9, .95), 1e-8, .01),
            decay={name: True for name in names}, max_norm=1.)
        accepted = resolve_candidate(transaction, accepted=True)
        bundle = derive_successor_bundle(
            student, accepted,
            parent_manifest_sha256=pointer["manifest_sha256"],
            delivery_events=({
                "event": "BAMF_GENERATION_ACCEPTED",
                "optimizer_step": accepted.optimizer_step},))
        published = accept_and_publish(
            run, bundle, accepted,
            feature_sha256=student.extents.factor_map_digest,
            retention_reason="COLD_RESUME_CONTINUATION_ACCEPTED",
            step_proofs=accepted.step_proofs)
    resumed["published"] = published
    resumed["successor_optimizer_step"] = accepted.optimizer_step
    resumed["successor_digest"] = retained_digest(accepted)
    resumed["successor_update_counts"] = {
        name: np.asarray(value).tolist()
        for name, value in sorted(accepted.optimizer.update_counts.items())}
    print(json.dumps(resumed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
