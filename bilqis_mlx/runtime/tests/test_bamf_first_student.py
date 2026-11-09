"""C16.1b first-student foundation preflight contract."""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import io
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import mlx.core as mx

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
import bilqis_mlx.runtime.model_topology_v2 as model_topology_v2
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.presentation.dashboard import build as build_dashboard
from bilqis_mlx.runtime.admission import _executable_factory_admission
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation_authority
from bilqis_mlx.runtime.bamf_first_student import (
    BAMF_DASHBOARD_METRICS_SCHEMA,
    BAMF_FOUNDATION_CONFIG_SCHEMA,
    BAMF_LAUNCH_RECEIPT_SCHEMA,
    BamfFoundationConfig,
    LaunchReceipt,
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

    def test_cli_reexports_foundation_contract_without_owning_dispatch(self):
        from bilqis_mlx import cli

        self.assertIs(cli.BamfFoundationConfig, BamfFoundationConfig)
        self.assertIs(cli.LaunchReceipt, LaunchReceipt)
        self.assertIs(cli.preflight_bamf_foundation, preflight_bamf_foundation)

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
            declared = model_topology_v2.expected_bamf_shapes(
                student.topology, student.extents)

        self.assertEqual(receipt.schema_version, BAMF_LAUNCH_RECEIPT_SCHEMA)
        self.assertEqual(receipt.config_schema_version, BAMF_FOUNDATION_CONFIG_SCHEMA)
        self.assertEqual(receipt.run_identity, student.run_identity)
        self.assertEqual(receipt.manifest_sha256, manifest_sha256)
        self.assertEqual(receipt.factory_release_sha256, self.release.release_sha256)
        self.assertEqual(receipt.run_identity.run_seed, 543)
        self.assertEqual(
            receipt.run_identity.initial_topology_digest, student.topology.digest)
        self.assertEqual(
            receipt.run_identity.initial_extents_digest, student.extents.digest)
        self.assertEqual(
            receipt.run_identity.initial_implementation_sha256,
            student.implementation_sha256)
        source_identity = (self.release.source_bindings.source_attestation_sha256
                           or self.release.source_bindings.digest())
        self.assertEqual(receipt.run_identity.initial_source_identity, source_identity)
        self.assertEqual(student.provenance.source_identity, source_identity)
        self.assertEqual(
            receipt.run_identity.initial_release_digest,
            student.provenance.release_digest)
        self.assertEqual(
            receipt.run_identity.initial_teacher_identity,
            student.provenance.teacher_identity)
        self.assertEqual(
            receipt.run_identity.initial_teacher_epoch,
            student.provenance.teacher_epoch)
        self.assertEqual(
            receipt.run_identity.factory_release_sha256,
            self.release.release_sha256)
        self.assertEqual(receipt.optimizer_hyperparameters, self.hp)
        self.assertEqual(student.optimizer_hyperparameters, self.hp)
        self.assertEqual(student.retained_state.optimizer_step, 0)
        self.assertEqual(student.retained_state.step_proofs, ())
        self.assertEqual(student.semantic_abi["schema"], "bilqis.mlx.bamf-semantic-abi/v1")
        self.assertGreater(student.semantic_abi["semantic_bank_count"], 0)
        self.assertEqual(
            student.semantic_abi["active_set_sha256"],
            student.extents.active_semantic_digest)
        expected_shapes = {item.name: item.shape for item in declared}
        actual_shapes = {
            name: tuple(value.shape)
            for name, value in student.retained_state.optimizer.parameters.items()
        }
        self.assertEqual(actual_shapes, expected_shapes)
        self.assertEqual(
            tuple(student.retained_state.optimizer.parameters),
            tuple(item.name for item in declared))
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
        self.assertEqual(
            student.teacher_state["teacher_identity"],
            student.provenance.teacher_identity)
        self.assertEqual(student.teacher_state["next_seed"], 543)
        self.assertEqual(receipt.atlas_artifact, self.identity)
        admitted_grades = tuple(
            grade.grade_id for grade in self.release.execution_plan.grades)
        self.assertEqual(
            tuple(student.compiler_features["factory_grade_ids"]), admitted_grades)
        self.assertEqual(receipt.dashboard_metrics.active_grades, admitted_grades)
        self.assertEqual(receipt.dashboard_metrics.current_grade, admitted_grades[0])
        self.assertEqual(receipt.dashboard_metrics.optimizer_step, 0)
        self.assertEqual(receipt.dashboard_metrics.grade_visits, 0)
        self.assertEqual(receipt.dashboard_metrics.stage, "READY_FOR_HUMAN_START")
        self.assertEqual(receipt.dashboard_metrics.last_run_status, "NOT_STARTED")
        self.assertEqual(
            receipt.dashboard_metrics.schema_version, BAMF_DASHBOARD_METRICS_SCHEMA)
        self.assertEqual(receipt.input_schema_versions, (
            ("config", BAMF_FOUNDATION_CONFIG_SCHEMA),
            ("factory_release", self.release.schema),
            ("atlas_artifact_identity", self.identity.schema),
        ))
        self.assertEqual(
            dict(receipt.output_schema_versions)["dashboard_metrics"],
            BAMF_DASHBOARD_METRICS_SCHEMA)
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

    def test_preflight_rejects_source_or_descendant_target_before_factory_replay(self):
        def file_digests():
            return {
                str(path.relative_to(self.source)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(self.source.rglob("*")) if path.is_file()
            }

        before = file_digests()
        for target in (self.source, self.source / "new-child"):
            with self.subTest(target=target), \
                    patch("bilqis_mlx.runtime.bamf_first_student."
                          "issue_initial_factory_foundation_authority") as factory_replay:
                with self.assertRaises(BilqisError) as failure:
                    self.preflight(target)

                self.assertEqual(
                    failure.exception.context["reason"],
                    "BAMF_FIRST_STUDENT_TARGET_OVERLAPS_SOURCE")
                factory_replay.assert_not_called()
                self.assertEqual(file_digests(), before)
                if target != self.source:
                    self.assertFalse(target.exists())

    def test_preflight_rejects_symlink_parent_target_resolving_inside_source(self):
        alias = self.root / "source-alias"
        alias.symlink_to(self.source, target_is_directory=True)
        target = alias / "new-child"
        before = {
            str(path.relative_to(self.source)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(self.source.rglob("*")) if path.is_file()
        }

        with patch("bilqis_mlx.runtime.bamf_first_student."
                   "issue_initial_factory_foundation_authority") as factory_replay:
            with self.assertRaises(BilqisError) as failure:
                self.preflight(target)

        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_FIRST_STUDENT_TARGET_OVERLAPS_SOURCE")
        factory_replay.assert_not_called()
        self.assertFalse((self.source / "new-child").exists())
        self.assertEqual({
            str(path.relative_to(self.source)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(self.source.rglob("*")) if path.is_file()
        }, before)

    def test_preflight_types_target_path_normalization_failure_before_factory_replay(self):
        with patch("bilqis_mlx.runtime.bamf_first_student."
                   "issue_initial_factory_foundation_authority") as factory_replay:
            with self.assertRaises(BilqisError) as failure:
                self.preflight(object())

        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_FIRST_STUDENT_TARGET_PATH_INVALID")
        factory_replay.assert_not_called()

    def test_preflight_types_source_path_expansion_failure_before_factory_replay(self):
        config = replace(
            self.config(), source_run_dir="~bilqis-no-such-user-543/source-run")
        target = self.root / "new-run"

        with patch("bilqis_mlx.runtime.bamf_first_student."
                   "issue_initial_factory_foundation_authority") as factory_replay:
            with self.assertRaises(BilqisError) as failure:
                self.preflight(target, config=config)

        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_FIRST_STUDENT_SOURCE_PATH_INVALID")
        factory_replay.assert_not_called()
        self.assertFalse(target.exists())

    def test_preflight_rejects_release_not_owned_by_current_factory_state(self):
        target = self.root / "new-run"
        foreign = replace(self.release, release_sha256="9" * 64)
        with self.assertRaises(BilqisError) as failure:
            self.preflight(target, release=foreign)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_FIRST_STUDENT_FACTORY_RELEASE_DRIFT")
        self.assertFalse(target.exists())

    def test_preflight_rejects_nested_semantic_graph_mutation_after_config_creation(self):
        config = self.config()
        config.semantic_graph["tokens"].append("caller-mutation")
        target = self.root / "new-run"

        with self.assertRaises(BilqisError) as failure:
            self.preflight(target, config=config)

        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_FIRST_STUDENT_SEMANTIC_GRAPH_DRIFT")
        self.assertFalse(target.exists())

    def test_preflight_preserves_source_run_bytes_while_publishing_only_target(self):
        def file_digests():
            return {
                str(path.relative_to(self.source)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(self.source.rglob("*")) if path.is_file()
            }

        before = file_digests()
        target = self.root / "new-run"
        self.preflight(target)
        self.assertEqual(file_digests(), before)
        self.assertTrue((target / "bamf-state.json").is_file())
        self.assertFalse((self.source / "bamf-state.json").exists())

    def test_published_generation_zero_is_immediately_visible_to_existing_dashboard(self):
        target = self.root / "new-run"
        self.preflight(target)
        admitted_grades = tuple(
            grade.grade_id for grade in self.release.execution_plan.grades)

        with shape_patch():
            board = build_dashboard(
                target, stream=io.StringIO(), reserve_gib=0.)

        self.assertEqual(board.state["step"], 0)
        self.assertEqual(board.state["visits"], 0)
        self.assertEqual(board.state["stop"], "NOT_STARTED")
        self.assertEqual(board.state["phase"], "READY_FOR_HUMAN_START")
        self.assertEqual(board.state["prefix"], admitted_grades[0])
        mastery = board.rows["GRADES & MASTERY"][-1]
        self.assertEqual(mastery["grade"], admitted_grades[0])
        self.assertEqual(mastery["step"], 0)
        self.assertEqual(mastery["outcome"], "READY_FOR_HUMAN_START")
        self.assertFalse((target / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
