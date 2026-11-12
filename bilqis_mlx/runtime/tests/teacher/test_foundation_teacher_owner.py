"""C16.3 production ownership of the accepted C03 teacher trajectory."""
from __future__ import annotations

import os
import random
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.compatibility import historical_teacher_policy
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.learning_experiment import Settings
from bilqis_mlx.runtime.accepted_teacher_custody import select_accepted_teacher_visit
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.foundation_teacher_owner import accepted_teacher_trajectory
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import publish_genesis, shape_patch
from bilqis_mlx.runtime.tests.custody.bamf_bundle.teacher_custody_fixtures import (
    adaptation, selection_teacher,
)


class FoundationTeacherOwnerTests(unittest.TestCase):
    def test_accepted_visit_owns_next_seed_and_opaque_cursor(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "run"
            with patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(root / "plane.sqlite3")}), \
                    shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
                publish_genesis(run, run_seed=71)
                parent = load_accepted_generation(run)
                school = SimpleNamespace(
                    stage="MAIN",
                    current_student=SimpleNamespace(
                        sha256=candidate_identity_digest(parent.retained_state)))
                bound, _policy, _metadata = select_accepted_teacher_visit(
                    run, historical_teacher_policy, school, random.Random(71),
                    Settings(), "factory/foundation", {}, "violet",
                    capability_id="C.ADD", total_capabilities=20,
                    legacy_receipt={"teacher": selection_teacher()},
                    adaptation=adaptation(), prior_region="legacy-region")
        trajectory = accepted_teacher_trajectory(bound)
        self.assertEqual(trajectory.next_seed, bound.identity.selection_seed + 1)
        self.assertEqual(trajectory.cursor, bound.identity.visit_id)
        self.assertNotEqual(trajectory.cursor, bound.identity.cursor)


if __name__ == "__main__":
    unittest.main()
