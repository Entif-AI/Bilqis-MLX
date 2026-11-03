"""Clean-process cold-resume probe used by the B13.2 continuation witness.

The probe owns no production authority. It reads the published generation
pointer, reconstructs the accepted generation from custody, executes the next
controlled optimizer step and publishes the successor generation. The parent
test compares the reconstructed state with the in-process state.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from bilqis_mlx.learning.atlas_acceptance import mint_acceptance_binding
from bilqis_mlx.runtime.bamf_bundle import (
    load_bamf_generation, publish_bamf_generation,
)

from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state, candidate, shape_patch,
)


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


def main(argv) -> int:
    run = Path(argv[1])
    pointer_path = run / "bamf-state.json"
    with shape_patch():
        student = load_bamf_generation(pointer_path)
        pointer = json.loads(pointer_path.read_text())
        resumed = {
            "generation": student.generation,
            "manifest_sha256": pointer["manifest_sha256"],
            "state_digest": retained_digest(student.retained_state),
            "teacher_state": dict(student.teacher_state),
            "optimizer_step": student.retained_state.optimizer_step,
        }
        successor_state = accepted_state(student.retained_state)
        successor = candidate(successor_state, student.generation + 1,
                              pointer["manifest_sha256"])
        published = publish_bamf_generation(
            run, successor, acceptance=mint_acceptance_binding(
                successor.retained_state, run_id=successor.run_id,
                generation=successor.generation,
                feature_sha256=successor.extents.factor_map_digest,
                retention_reason="FIXTURE_RETENTION_ACCEPTED"))
    resumed["published"] = published
    resumed["successor_optimizer_step"] = successor_state.optimizer_step
    resumed["successor_digest"] = retained_digest(successor_state)
    print(json.dumps(resumed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
