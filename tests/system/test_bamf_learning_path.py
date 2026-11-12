"""C13.1 source-fixture and disposable-delivery preflight contracts."""
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from scripts.prove_bamf_delivery import (
    DeliveryConfig, EpisodeSourceRelease, check_episode_binding,
    episode_binding_case, prove_bamf_delivery,
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
        self.assertTrue(visible["task_goal_shape"]["gold_binding_in_model_input"] is False)
        self.assertIn("ROLE_LOOKUP", visible["task_goal_shape"]["continuation"])
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
        self.assertEqual(receipt.exercised_behaviors, ("DISPOSABLE_CREATION",))
        self.assertEqual(receipt.baseline_case_count, 64)
        self.assertEqual(receipt.fresh_case_count, 64)
        self.assertEqual(
            [row["input"]["seed"] for row in payload["baseline"]], list(range(64)))
        self.assertEqual(
            [row["input"]["seed"] for row in payload["fresh"]], list(range(64, 128)))
        self.assertEqual(
            set(receipt.remaining_behaviors),
            {"SOURCE_BOUND_GRADIENTS", "PAIRED_EVALUATION", "ACCEPTED_CANDIDATE",
             "REJECTED_CANDIDATE", "COLD_RESTART", "APPEND_ONLY_SEMANTIC_DELTA"},
        )
        self.assertTrue(all("target_actor" not in json.dumps(row["input"])
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


if __name__ == "__main__":
    unittest.main()
