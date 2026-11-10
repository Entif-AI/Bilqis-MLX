"""C16.1b first-student foundation preflight contract."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import io
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.model_topology_v2 as model_topology_v2
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.presentation.dashboard import build as build_dashboard
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation_authority
from bilqis_mlx.runtime.bamf_first_student import (
    BamfFoundationConfig,
    LaunchReceipt,
    preflight_bamf_foundation,
)
from bilqis_mlx.runtime.tests._bamf_first_student_support import BamfFirstStudentCase
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch
from bilqis_mlx.semantics.tests.core.test_atlas_export_clearance import REGISTRY


class BamfFirstStudentTests(BamfFirstStudentCase):
    def test_cli_reexports_foundation_contract_without_owning_dispatch(self):
        from bilqis_mlx import cli

        self.assertIs(cli.BamfFoundationConfig, BamfFoundationConfig)
        self.assertIs(cli.LaunchReceipt, LaunchReceipt)
        self.assertIs(cli.preflight_bamf_foundation, preflight_bamf_foundation)

    def test_preflight_publishes_exact_owner_bound_zero_update_foundation(self):
        target = self.root / "new-run"
        receipt = self.preflight(target)
        with shape_patch():
            student, manifest_sha256 = load_bamf_generation_authority(
                target / "bamf-state.json")
            declared = model_topology_v2.expected_bamf_shapes(
                student.topology, student.extents)
        self.assert_owner_identity(receipt, student, manifest_sha256)
        self.assert_zero_optimizer_and_semantics(receipt, student, declared)
        self.assert_teacher_and_dashboard(receipt, student, target)

    def test_preflight_consumes_fixed_host_source_authority_without_target_provisioning(self):
        target = self.root / "host-rooted-run"
        self.preflight(target)

        with shape_patch():
            student, _manifest_sha256 = load_bamf_generation_authority(
                target / "bamf-state.json")
            from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
            authority = AcceptedRuntimeHost(target).source_authority()
            from bilqis_mlx.runtime.bamf_bundle.admission import (
                bind_accepted_execution_cache,
            )
            cache = bind_accepted_execution_cache(target)
            from bilqis_mlx.runtime.atlas_revalidation import (
                require_source_authority_runtime,
            )
            self.assertIs(require_source_authority_runtime(authority, cache), authority)

        self.assertEqual(
            student.correction_frontier["source_authority_registry_sha256"],
            REGISTRY.digest,
        )
        self.assertEqual(
            student.correction_frontier["source_authority_registry_origin"],
            "HOST_SYSTEM_V1",
        )
        self.assertFalse((target / "source-authority-registry.json").exists())

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
            with self.subTest(target=str(target)), \
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
        self.assertEqual(board.grade_program, admitted_grades)
        mastery = board.rows["GRADES & MASTERY"][-1]
        self.assertEqual(mastery["grade"], admitted_grades[0])
        self.assertEqual(mastery["step"], 0)
        self.assertEqual(mastery["outcome"], "READY_FOR_HUMAN_START")
        self.assertFalse((target / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
