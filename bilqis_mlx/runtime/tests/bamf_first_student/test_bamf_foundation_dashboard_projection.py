"""C16.1b persisted generation-zero dashboard projection boundary."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError, SCHOOL
from bilqis_mlx.runtime.bamf_bundle.genesis.records import BamfRunIdentity
from bilqis_mlx.runtime.bamf_first_student import (
    BamfFoundationDashboardProjection,
    load_bamf_foundation_dashboard_projection,
)


def _identity() -> BamfRunIdentity:
    return BamfRunIdentity(
        run_id="dashboard-fixture",
        run_seed=7,
        origin_checkpoint_sha256="1" * 64,
        origin_checkpoint_filename="bundles/origin",
        origin_optimizer_step=0,
        factory_release_sha256="2" * 64,
        semantic_graph_sha256="3" * 64,
        initial_candidate_identity_sha256="4" * 64,
        initial_topology_digest="5" * 64,
        initial_extents_digest="6" * 64,
        initial_implementation_sha256="7" * 64,
        initial_source_identity="fixture-source",
        initial_release_digest="8" * 64,
        initial_teacher_identity="fixture-teacher",
        initial_teacher_epoch=0,
    )


def _student(**changes):
    identity = _identity()
    values = {
        "generation": 0,
        "run_id": identity.run_id,
        "run_identity": identity,
        "retained_state": SimpleNamespace(optimizer_step=0),
        "compiler_features": {
            "factory_release_sha256": identity.factory_release_sha256,
            "factory_grade_ids": ["A", "B", "C"],
        },
        "teacher_state": {
            "teacher_identity": identity.initial_teacher_identity,
            "teacher_epoch": 0,
            "next_seed": identity.run_seed,
            "cursor": "GENESIS",
        },
    }
    values.update(changes)
    return SimpleNamespace(**values)


class BamfFoundationDashboardProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.pointer = self.root / "bamf-state.json"

    def tearDown(self):
        self.temporary.cleanup()

    def test_absent_pointer_is_the_only_none_result(self):
        self.assertIsNone(load_bamf_foundation_dashboard_projection(self.root))

    def test_malformed_run_dir_is_typed_at_projection_boundary(self):
        with self.assertRaises(BilqisError) as failure:
            load_bamf_foundation_dashboard_projection(object())
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_FIRST_STUDENT_DASHBOARD_PATH_INVALID")

    def test_exact_generation_zero_projection_is_immutable(self):
        self.pointer.write_text("fixture")
        with patch(
                "bilqis_mlx.runtime.bamf_first_student.load_bamf_generation_authority",
                return_value=(_student(), "9" * 64)):
            projection = load_bamf_foundation_dashboard_projection(self.root)

        self.assertEqual(projection, BamfFoundationDashboardProjection(
            factory_release_sha256="2" * 64,
            optimizer_step=0,
            grade_visits=0,
            teacher_events=0,
            stage="READY_FOR_HUMAN_START",
            active_grades=("A", "B", "C"),
            current_grade="A",
            last_run_status="NOT_STARTED",
        ))
        with self.assertRaises(AttributeError):
            projection.optimizer_step = 1

    def test_present_invalid_pointer_fails_closed(self):
        self.pointer.write_text("broken")
        with patch(
                "bilqis_mlx.runtime.bamf_first_student.load_bamf_generation_authority",
                side_effect=BilqisError(
                    SCHOOL.BAMF_FIRST_STUDENT.INVALID, {"reason": "fixture"})):
            with self.assertRaises(BilqisError):
                load_bamf_foundation_dashboard_projection(self.root)

    def test_nonzero_generation_is_rejected(self):
        self.pointer.write_text("fixture")
        with patch(
                "bilqis_mlx.runtime.bamf_first_student.load_bamf_generation_authority",
                return_value=(_student(generation=1), "9" * 64)):
            with self.assertRaises(BilqisError) as failure:
                load_bamf_foundation_dashboard_projection(self.root)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_FIRST_STUDENT_DASHBOARD_PROJECTION_INVALID")

    def test_non_genesis_teacher_state_is_rejected(self):
        self.pointer.write_text("fixture")
        teacher = dict(_student().teacher_state)
        teacher["cursor"] = "TRAINING"
        with patch(
                "bilqis_mlx.runtime.bamf_first_student.load_bamf_generation_authority",
                return_value=(_student(teacher_state=teacher), "9" * 64)):
            with self.assertRaises(BilqisError) as failure:
                load_bamf_foundation_dashboard_projection(self.root)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_FIRST_STUDENT_DASHBOARD_PROJECTION_INVALID")

    def test_malformed_foundation_metadata_is_rejected(self):
        self.pointer.write_text("fixture")
        compiler = dict(_student().compiler_features)
        compiler["factory_grade_ids"] = []
        with patch(
                "bilqis_mlx.runtime.bamf_first_student.load_bamf_generation_authority",
                return_value=(_student(compiler_features=compiler), "9" * 64)):
            with self.assertRaises(BilqisError) as failure:
                load_bamf_foundation_dashboard_projection(self.root)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_FIRST_STUDENT_DASHBOARD_PROJECTION_INVALID")


if __name__ == "__main__":
    unittest.main()
