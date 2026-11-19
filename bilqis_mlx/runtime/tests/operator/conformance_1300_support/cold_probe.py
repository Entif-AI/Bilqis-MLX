"""Clean-process custody probe for the #1300 integrated witness."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from bilqis_mlx.runtime.active_grade_cadence import read_current_cadence
from bilqis_mlx.runtime.active_generated_grade import read_active_generated_grade
from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_factory_release
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime.tests.custody.bamf_bundle.cold_resume_probe import (
    retained_digest,
)


def probe(run_dir: Path) -> dict:
    accepted = load_accepted_generation(run_dir)
    release = read_accepted_atlas_factory_release(run_dir)
    active_grade = read_active_generated_grade(run_dir)
    cadence = read_current_cadence(run_dir)
    return {
        "generation": accepted.generation,
        "optimizer_step": accepted.retained_state.optimizer_step,
        "checkpoint_identity_sha256": candidate_identity_digest(
            accepted.retained_state
        ),
        "topology_sha256": accepted.topology.digest,
        "topology_layers": accepted.topology.layers,
        "retained_digest": retained_digest(accepted.retained_state),
        "baseline_evidence": accepted.baseline_evidence,
        "teacher_state": accepted.teacher_state,
        "factory_release_sha256": release.release_sha256,
        "active_grade": active_grade.to_record(),
        "cadence": None if cadence is None else cadence.to_record(),
    }


def main(argv: list[str]) -> int:
    print(json.dumps(probe(Path(argv[1])), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
