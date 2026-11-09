"""C16.1b first-student foundation preflight contract."""
from __future__ import annotations

from dataclasses import asdict, replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import mlx.core as mx

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.admission import _executable_factory_admission
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation_authority
from bilqis_mlx.runtime.bamf_first_student import (
    BAMF_FOUNDATION_CONFIG_SCHEMA,
    BAMF_LAUNCH_RECEIPT_SCHEMA,
    BamfFoundationConfig,
    preflight_bamf_foundation,
)
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.runtime.tests.custody.bamf_bundle.genesis_authority_fixtures import (
    ATLAS_BUNDLE,
    ATLAS_RELEASE,
    SOURCE_BUNDLE,
    genesis_feature_source_patch,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch
from bilqis_mlx.runtime.tests.operator.test_admission import _executable_fixture
from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactIdentity,
    AtlasArtifactSelection,
)
from bilqis_mlx.state_dag import persist


class BamfFirstStudentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()
        self.release, self.graph = _executable_fixture()
        self.source = self.root / "source-run"
        origin = Checkpoint("7" * 64, "bundles/foundation-origin", 0, True)
        _, release_file, admission = _executable_factory_admission(
            self.source, self.release, origin, _fingerprint(self.graph), self.graph)
        state = {
            "generation": 0,
            "factory_release_sha256": self.release.release_sha256,
            "factory_release_file": release_file,
            "factory_admission_v2": asdict(admission),
            "semantic_graph_sha256": _fingerprint(self.graph),
            "school": {
                "current_student": asdict(origin),
                "active_grades": ["A", "B", "C"],
                "grade_index": 2,
                "visits": 11,
                "stage": "FOUNDATION",
            },
            "result": "READY_FOR_HUMAN_START",
        }
        persist(self.source, state)
        self.hp = AdamWHyperparameters(.0007, (.88, .97), 1e-7, .03)
        self.identity = AtlasArtifactIdentity(
            ATLAS_BUNDLE, ATLAS_RELEASE, SOURCE_BUNDLE)
        self.selection = AtlasArtifactSelection(
            "/fixture/atlas", ATLAS_BUNDLE, ATLAS_RELEASE, SOURCE_BUNDLE)

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def config(self, *, run_id="bamf-first-student", run_seed=543):
        return BamfFoundationConfig(
            source_run_dir=str(self.source),
            run_id=run_id,
            run_seed=run_seed,
            semantic_graph=self.graph,
            atlas_artifact=self.identity,
            optimizer_hyperparameters=self.hp,
        )

    def preflight(self, target: Path, *, config=None, release=None):
        config = self.config() if config is None else config
        release = self.release if release is None else release
        with shape_patch(), genesis_feature_source_patch(), \
                patch("bilqis_mlx.runtime.bamf_first_student.resolve_atlas_artifact_selection",
                      return_value=self.selection), \
                patch.object(mlx_checkpoint, "assert_headroom"):
            return preflight_bamf_foundation(config, release, target)

    def test_preflight_publishes_exact_owner_bound_zero_update_foundation(self):
        target = self.root / "new-run"
        receipt = self.preflight(target)
        with shape_patch():
            student, manifest_sha256 = load_bamf_generation_authority(
                target / "bamf-state.json")

        self.assertEqual(receipt.schema_version, BAMF_LAUNCH_RECEIPT_SCHEMA)
        self.assertEqual(receipt.config_schema_version, BAMF_FOUNDATION_CONFIG_SCHEMA)
        self.assertEqual(receipt.run_identity, student.run_identity)
        self.assertEqual(receipt.manifest_sha256, manifest_sha256)
        self.assertEqual(receipt.factory_release_sha256, self.release.release_sha256)
        self.assertEqual(receipt.run_identity.run_seed, 543)
        self.assertEqual(receipt.optimizer_hyperparameters, self.hp)
        self.assertEqual(student.optimizer_hyperparameters, self.hp)
        self.assertEqual(student.retained_state.optimizer_step, 0)
        self.assertEqual(student.retained_state.step_proofs, ())
        self.assertTrue(all(
            not bool(mx.any(moment))
            for tree in (student.retained_state.optimizer.m,
                         student.retained_state.optimizer.v)
            for moment in tree.values()))
        self.assertTrue(all(
            not bool(mx.any(count))
            for count in student.retained_state.optimizer.update_counts.values()))
        self.assertEqual(
            student.teacher_state["teacher_identity"],
            self.release.execution_plan.projection_digests.teaching)
        self.assertEqual(student.teacher_state["next_seed"], 543)
        self.assertEqual(receipt.atlas_artifact, self.identity)
        self.assertEqual(receipt.dashboard_metrics.active_grades, ("A", "B", "C"))
        self.assertEqual(receipt.dashboard_metrics.current_grade, "C")
        self.assertEqual(receipt.dashboard_metrics.optimizer_step, 0)
        self.assertEqual(receipt.dashboard_metrics.grade_visits, 11)
        self.assertEqual(receipt.dashboard_metrics.stage, "FOUNDATION")
        self.assertEqual(receipt.dashboard_metrics.last_run_status, "READY_FOR_HUMAN_START")
        self.assertEqual(receipt.optional_services_required, ())
        for optional in ("akasha", "low-bit-cache", "private-journal"):
            self.assertFalse((target / optional).exists())

    def test_preflight_rejects_occupied_run_directory_without_touching_it(self):
        target = self.root / "old-run"
        target.mkdir()
        sentinel = target / "existing-student"
        sentinel.write_text("keep")

        with self.assertRaises(BilqisError) as failure:
            self.preflight(target)

        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_FIRST_STUDENT_RUN_DIRECTORY_OCCUPIED")
        self.assertEqual(sentinel.read_text(), "keep")
        self.assertEqual(tuple(target.iterdir()), (sentinel,))

    def test_preflight_rejects_release_not_owned_by_current_factory_state(self):
        target = self.root / "new-run"
        foreign = replace(self.release, release_sha256="9" * 64)
        with self.assertRaises(BilqisError) as failure:
            self.preflight(target, release=foreign)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_FIRST_STUDENT_FACTORY_RELEASE_DRIFT")
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
