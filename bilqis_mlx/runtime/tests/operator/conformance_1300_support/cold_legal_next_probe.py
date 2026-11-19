"""Fresh-process production-owner probe for the exact next lawful #1300 visit."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

from bilqis_mlx.data_plane import close_data_planes
from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime.accepted_priority_visit import accepted_priority_school
from bilqis_mlx.runtime.active_generated_grade import read_active_generated_grade
from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_factory_release
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.bamf_operator.session import _execution_context
from bilqis_mlx.runtime.foundation_teacher_owner import select_foundation_priority_visit
from bilqis_mlx.runtime.accepted_priority_visit import require_priority_lawful_frontier
from bilqis_mlx.runtime.active_grade_cadence import read_current_cadence
from bilqis_mlx.runtime.autonomy_state import read_autonomy_state
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_delta_adapter_fixtures import (
    AtlasDeltaAdapterFixture,
)

from .runtime import Conformance1300RuntimeSupport


def _autonomy_identity(run_dir: Path, release):
    pointer_path = run_dir / "autonomy" / "current.json"
    if pointer_path.is_symlink() or not pointer_path.is_file():
        return None
    plan, ledger = read_autonomy_state(run_dir, release)
    pointer = json.loads(pointer_path.read_text())
    return {
        "state_sha256": pointer["state_sha256"],
        "plan_sha256": plan.digest(),
        "receipt_count": len(ledger.receipts),
        "intervention_count": len(ledger.interventions),
        "rejected_attempt_count": len(ledger.rejected_attempts),
    }


def probe(run_dir: Path) -> dict:
    run_dir = run_dir.resolve()
    data_plane = run_dir.parent / "plane.sqlite3"
    case = Conformance1300RuntimeSupport(methodName="runTest")
    case.run = run_dir
    case.z = AtlasDeltaAdapterFixture()
    case.z.setUp()
    case.z.doCleanups()
    with patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(data_plane)}):
        close_data_planes()
        try:
            fixture = case._source_fixture()
            before = load_accepted_generation(run_dir)
            release_before = read_accepted_atlas_factory_release(run_dir)
            autonomy_before = _autonomy_identity(run_dir, release_before)
            cadence_before = read_current_cadence(run_dir)
            with case._operator_context(fixture):
                parent, context, atlas_path, _feature_path = _execution_context(run_dir)
                program = schedule_program_from_executable_release(context.release)
                school = accepted_priority_school(parent, program)
                selected = select_foundation_priority_visit(
                    run_dir,
                    context,
                    atlas_path,
                    program=program,
                    school=school,
                )
                frontier = require_priority_lawful_frontier(selected)
                active = read_active_generated_grade(run_dir)
                release = read_accepted_atlas_factory_release(run_dir)
            cadence_after = read_current_cadence(run_dir)
            autonomy_after = _autonomy_identity(run_dir, release)
            after = load_accepted_generation(run_dir)
        finally:
            close_data_planes()
    return {
        "generation": after.generation,
        "optimizer_step": after.retained_state.optimizer_step,
        "checkpoint_identity_sha256": candidate_identity_digest(after.retained_state),
        "factory_release_sha256": release.release_sha256,
        "active_grade": active.to_record(),
        "cadence_before": (
            None if cadence_before is None else cadence_before.to_record()
        ),
        "cadence_after": (
            None if cadence_after is None else cadence_after.to_record()
        ),
        "autonomy_before": autonomy_before,
        "autonomy_after": autonomy_after,
        "lawful_frontier_sha256": frontier.frontier_sha256,
        "frontier_checkpoint_identity_sha256": frontier.accepted_checkpoint_sha256,
        "frontier_factory_release_sha256": frontier.admitted_release_sha256,
        "frontier_active_grade_activation_sha256": (
            frontier.active_grade_activation_sha256
        ),
        "legal_next_status": selected.status,
        "legal_next_capability_id": selected.option_id,
        "legal_next_grade": selected.lesson_grade,
        "legal_next_visit_identity": (
            None if selected.visit is None else selected.visit.identity.to_record()
        ),
        "accepted_state_unchanged": (
            before.generation == after.generation
            and before.retained_state.optimizer_step == after.retained_state.optimizer_step
            and candidate_identity_digest(before.retained_state)
            == candidate_identity_digest(after.retained_state)
        ),
    }


def main(argv: list[str]) -> int:
    print(json.dumps(probe(Path(argv[1])), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
