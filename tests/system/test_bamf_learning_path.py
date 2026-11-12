"""C13.1 source-fixture and disposable-delivery preflight contracts."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.tests.bamf_first_student._bamf_first_student_support import (
    BamfFirstStudentCase,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.genesis_authority_fixtures import (
    ATLAS_RELEASE, genesis_feature_source_patch,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch
from scripts.prove_bamf_delivery import (
    DeliveryConfig, EpisodeSourceRelease, check_episode_binding,
    episode_binding_case, episode_task_goal, FoundationLaunchInput,
    prove_bamf_delivery,
)


class BamfLearningPathFixtureTests(unittest.TestCase):
    def setUp(self):
        self.config = DeliveryConfig()
        self.source = EpisodeSourceRelease("a" * 64, "b" * 64)

    def test_episode_fixture_is_deterministic_gold_blind_and_constructive(self):
        first = episode_binding_case(7)
        self.assertEqual(first, episode_binding_case(7))
        self.assertNotEqual(first, episode_binding_case(8))
        visible = first.source_view()
        self.assertEqual(visible["actors"], ["A", "B", "C"])
        self.assertEqual(len(visible["events"]), 6)
        self.assertEqual(
            sorted((row["actor"], row["ordinal"]) for row in visible["events"]),
            [(actor, ordinal) for actor in ("A", "B", "C") for ordinal in (0, 1)],
        )
        wire = json.dumps(visible, sort_keys=True)
        self.assertNotIn("checker_answer", wire)
        self.assertNotIn("target_actor", wire)
        goal = episode_task_goal(first, self.source.semantic_release)
        self.assertEqual(goal.output_signature, "Number")
        self.assertEqual(goal.allowed_operator_ids, ("ADD", "SELECT_NUMBER"))
        self.assertTrue(all("duration:" in item for item in goal.source_visible_bindings))
        self.assertGreater(check_episode_binding(first), 0)

    def test_depth_changes_binding_without_exposing_selected_actor(self):
        answers = [check_episode_binding(episode_binding_case(22, depth))
                   for depth in (1, 2, 3, 4)]
        self.assertGreater(len(set(answers)), 1)
        for depth in (1, 2, 3, 4):
            view = episode_binding_case(22, depth).source_view()
            self.assertEqual(view["relation_cue"]["hops"], depth)
            self.assertNotIn("target_actor", view)

    def test_preflight_writes_exact_seed_split_and_truthful_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = prove_bamf_delivery(self.config, self.source, directory, 64)
            payload = json.loads(
                (Path(directory) / "c13-source-fixtures.json").read_text())
        self.assertEqual(receipt.status, "PREPARED")
        self.assertEqual(receipt.exercised_behaviors, ("SOURCE_FIXTURES",))
        self.assertIsNone(receipt.launch_receipt)
        self.assertIsNone(receipt.run_dir)
        self.assertEqual(receipt.baseline_case_count, 64)
        self.assertEqual(receipt.fresh_case_count, 64)
        self.assertEqual(
            [row["input"]["seed"] for row in payload["baseline"]], list(range(64)))
        self.assertEqual(
            [row["input"]["seed"] for row in payload["fresh"]], list(range(64, 128)))
        self.assertEqual(
            set(receipt.remaining_behaviors),
            {"DISPOSABLE_CREATION", "SOURCE_BOUND_GRADIENTS", "PAIRED_EVALUATION", "ACCEPTED_CANDIDATE",
             "REJECTED_CANDIDATE", "COLD_RESTART", "APPEND_ONLY_SEMANTIC_DELTA"},
        )
        self.assertTrue(all("target_actor" not in json.dumps(row["input"])
                            for row in payload["baseline"] + payload["fresh"]))
        self.assertTrue(all(row["task_goal"]["schema_version"] == "bilqis.task-goal/v1"
                            for row in payload["baseline"] + payload["fresh"]))

    def test_preflight_is_reproducible_and_bounded_to_64_steps(self):
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            left = prove_bamf_delivery(self.config, self.source, one, 0)
            right = prove_bamf_delivery(self.config, self.source, two, 64)
        self.assertEqual(left.fixture_manifest_sha256, right.fixture_manifest_sha256)
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(BilqisError):
            prove_bamf_delivery(self.config, self.source, directory, 65)

    def test_retained_run_tree_is_rejected(self):
        retained = Path(__file__).resolve().parents[2] / "runs" / "school-mlx-v1"
        with self.assertRaises(BilqisError):
            prove_bamf_delivery(self.config, self.source, retained, 1)


class BamfLearningPathFoundationTests(BamfFirstStudentCase):
    def test_integrated_preflight_publishes_real_zero_update_disposable_foundation(self):
        source = EpisodeSourceRelease(
            self.release.release_sha256,
            ATLAS_RELEASE,
            FoundationLaunchInput(self.config(run_id="c13-disposable"), self.release),
        )
        target = self.root / "c13-delivery"
        with shape_patch(), genesis_feature_source_patch(), patch(
                "bilqis_mlx.runtime.bamf_first_student.resolve_atlas_artifact_selection",
                return_value=self.selection), patch.object(
                mlx_checkpoint, "assert_headroom"), patch(
                "bilqis_mlx.runtime.bamf_bundle.codec.assert_headroom"):
            receipt = prove_bamf_delivery(DeliveryConfig(), source, target, 0)

        self.assertEqual(receipt.status, "FOUNDATION_CREATED")
        self.assertEqual(
            receipt.exercised_behaviors,
            ("SOURCE_FIXTURES", "DISPOSABLE_CREATION"),
        )
        self.assertNotIn("DISPOSABLE_CREATION", receipt.remaining_behaviors)
        self.assertEqual(receipt.launch_receipt.dashboard_metrics.optimizer_step, 0)
        self.assertEqual(
            receipt.launch_receipt.factory_release_sha256,
            self.release.release_sha256,
        )
        self.assertTrue((Path(receipt.run_dir) / "bamf-state.json").is_file())
        self.assertTrue((target / "c13-source-fixtures.json").is_file())


if __name__ == "__main__":
    unittest.main()
