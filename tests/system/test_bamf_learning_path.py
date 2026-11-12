"""C13.1 source-fixture and disposable-delivery preflight contracts."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
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
from scripts.bamf.c13_delivery_contracts import CandidateAttemptReceipt
from scripts.bamf import c13_delivery_runtime as delivery_runtime
from scripts.bamf.c13_episode_source import (
    CAPABILITY, episode_factory_release, registered_episode_lowerer,
)
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
        self.assertNotIn("COLD_RESTART", receipt.exercised_behaviors)
        self.assertIn("COLD_RESTART", receipt.remaining_behaviors)
        self.assertEqual(
            receipt.launch_receipt.factory_release_sha256,
            self.release.release_sha256,
        )
        self.assertTrue((Path(receipt.run_dir) / "bamf-state.json").is_file())
        self.assertTrue((target / "c13-source-fixtures.json").is_file())

    def test_integrated_receipt_names_real_candidate_behaviors_only_after_owner_attempts(self):
        source = EpisodeSourceRelease(
            self.release.release_sha256,
            ATLAS_RELEASE,
            FoundationLaunchInput(self.config(run_id="c13-attempts"), self.release),
        )
        attempts = (
            CandidateAttemptReceipt("ACCEPTED", 0, 1, 0, 1, "1" * 64, "2" * 64, 1),
            CandidateAttemptReceipt("REJECTED", 1, 1, 1, 1, "2" * 64, "2" * 64, 1),
        )
        with shape_patch(), genesis_feature_source_patch(), patch(
                "bilqis_mlx.runtime.bamf_first_student.resolve_atlas_artifact_selection",
                return_value=self.selection), patch.object(
                mlx_checkpoint, "assert_headroom"), patch(
                "bilqis_mlx.runtime.bamf_bundle.codec.assert_headroom"), patch(
                "scripts.prove_bamf_delivery.run_candidate_attempts",
                return_value=attempts), patch(
                "scripts.prove_bamf_delivery.cold_restart_identity",
                return_value={"candidate_identity_sha256": "2" * 64}):
            receipt = prove_bamf_delivery(DeliveryConfig(), source, self.root / "attempts", 2)

        self.assertEqual(receipt.status, "CANDIDATE_EXERCISED")
        self.assertEqual(receipt.candidate_attempts, attempts)
        self.assertEqual(
            set(receipt.exercised_behaviors),
            {"SOURCE_FIXTURES", "DISPOSABLE_CREATION", "SOURCE_BOUND_GRADIENTS",
             "PAIRED_EVALUATION", "ACCEPTED_CANDIDATE", "REJECTED_CANDIDATE",
             "COLD_RESTART"},
        )
        self.assertEqual(
            receipt.remaining_behaviors,
            ("APPEND_ONLY_SEMANTIC_DELTA",),
        )


class BamfLearningPathCandidateAccountingTests(unittest.TestCase):
    @staticmethod
    def student(generation, step):
        return SimpleNamespace(
            generation=generation,
            retained_state=SimpleNamespace(optimizer_step=step),
        )

    def test_owner_candidate_acceptance_must_advance_generation_and_optimizer(self):
        parent, current = self.student(0, 0), self.student(1, 1)
        result = SimpleNamespace(status="VISIT_LIMIT", visits=1, accepted=1, rejected=0)
        with patch.object(
                delivery_runtime, "load_accepted_generation",
                side_effect=(parent, current)), patch.object(
                delivery_runtime, "operate_bamf", return_value=result) as operate, patch.object(
                delivery_runtime, "_identity", side_effect=("1" * 64, "2" * 64)):
            receipt = delivery_runtime.attempt_owner_candidate(Path("/tmp/disposable"))
        self.assertEqual(receipt.outcome, "ACCEPTED")
        self.assertEqual(receipt.attempted_steps, 1)
        self.assertEqual((receipt.current_generation, receipt.current_optimizer_step), (1, 1))
        self.assertEqual(operate.call_args.kwargs["reserve_gib"], 100.0)

    def test_owner_candidate_rejection_and_hold_preserve_accepted_parent(self):
        cases = (
            (SimpleNamespace(status="REJECTED_HOLD", visits=1, accepted=0, rejected=1),
             "REJECTED", 1),
            (SimpleNamespace(status="PRIORITY_HOLD", visits=0, accepted=0, rejected=0),
             "HELD", 0),
        )
        for result, expected, attempted in cases:
            with self.subTest(outcome=expected):
                parent, current = self.student(3, 7), self.student(3, 7)
                with patch.object(
                        delivery_runtime, "load_accepted_generation",
                        side_effect=(parent, current)), patch.object(
                        delivery_runtime, "operate_bamf", return_value=result), patch.object(
                        delivery_runtime, "_identity", side_effect=("3" * 64, "3" * 64)):
                    receipt = delivery_runtime.attempt_owner_candidate(Path("/tmp/disposable"))
                self.assertEqual(receipt.outcome, expected)
                self.assertEqual(receipt.attempted_steps, attempted)

    def test_candidate_loop_stops_at_first_rejection_after_acceptance(self):
        accepted = CandidateAttemptReceipt(
            "ACCEPTED", 0, 1, 0, 1, "1" * 64, "2" * 64, 1)
        rejected = CandidateAttemptReceipt(
            "REJECTED", 1, 1, 1, 1, "2" * 64, "2" * 64, 1)
        with patch.object(
                delivery_runtime, "attempt_owner_candidate",
                side_effect=(accepted, rejected, AssertionError("must stop"))):
            attempts = delivery_runtime.run_candidate_attempts(Path("/tmp/disposable"), 64)
        self.assertEqual(attempts, (accepted, rejected))

    def test_cold_restart_identity_uses_fresh_process_and_preserves_full_candidate_digest(self):
        parent = self.student(4, 9)
        with patch.object(
                delivery_runtime, "load_accepted_generation", return_value=parent), patch.object(
                delivery_runtime, "_identity", return_value="7" * 64), patch.object(
                delivery_runtime.subprocess, "run") as run:
            run.return_value = SimpleNamespace(
                returncode=0, stderr="",
                stdout=json.dumps({
                    "generation": 4,
                    "optimizer_step": 9,
                    "candidate_identity_sha256": "7" * 64,
                }) + "\n")
            receipt = delivery_runtime.cold_restart_identity(Path("/tmp/disposable"))
        self.assertEqual(receipt["candidate_identity_sha256"], "7" * 64)
        self.assertIn("-c", run.call_args.args[0])


class BamfLearningPathSemanticDeltaTests(unittest.TestCase):
    def test_c13_semantic_delta_composition_preserves_prior_optimizer_prefix(self):
        import numpy as np

        RowAge = __import__(
            "bilqis_mlx.learning._retention._atlas_plasticity_base",
            fromlist=["IdentityRowAge"],
        ).IdentityRowAge
        parent_policy = SimpleNamespace(row_ages=(RowAge(0, 0, 7),))
        current_policy = SimpleNamespace(
            row_ages=(RowAge(0, 0, 7), RowAge(0, 1, 0)))
        before = np.arange(6, dtype=np.float32).reshape(2, 3)
        after = np.vstack((before, np.asarray([[11, 12, 13]], dtype=np.float32)))
        zero_before = np.zeros_like(before)
        zero_after = np.vstack((zero_before, np.zeros((1, 3), dtype=np.float32)))
        counts_before = np.zeros_like(before, dtype=np.int64)
        counts_after = np.vstack((counts_before, np.zeros((1, 3), dtype=np.int64)))

        def student(generation, policy, params, m, v, counts):
            optimizer = SimpleNamespace(
                parameters={"identity.bank.0": params},
                m={"identity.bank.0": m},
                v={"identity.bank.0": v},
                update_counts={"identity.bank.0": counts},
            )
            return SimpleNamespace(
                generation=generation,
                retained_state=SimpleNamespace(
                    optimizer_step=9, optimizer=optimizer, policy=policy))

        parent = student(4, parent_policy, before, zero_before, zero_before, counts_before)
        current = student(5, current_policy, after, zero_after, zero_after, counts_after)
        receipt = delivery_runtime.record_append_only_semantic_delta(
            parent, current, "new.semantic")
        self.assertEqual(receipt.parent_generation, 4)
        self.assertEqual(receipt.current_generation, 5)
        self.assertEqual(receipt.optimizer_step, 9)
        self.assertEqual(receipt.new_rows, ((0, 1),))


class BamfLearningPathEpisodeSourceTests(unittest.TestCase):
    def test_disposable_episode_provider_compiles_and_redraws_through_factory(self):
        from bilqis_mlx.runtime.source_execution import SourceExecutionContext

        release, graph, sources, answers = episode_factory_release()
        context = SourceExecutionContext(release, graph, None, sources, answers)
        rows = tuple(context.draw_rows(seed=31, capability=CAPABILITY, each=4))
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(sources.resolve_owner(row["generator"]).check(row)
                            for row in rows))
        authority = context.bind_rows(rows, seed=31, capability=CAPABILITY, each=4)
        self.assertEqual(authority.release_sha256, release.release_sha256)
        self.assertEqual(authority.source_family_id, "bamf.c13.episode-binding/v1")

    def test_episode_lowerer_is_gold_blind_and_resolves_binding_by_actor_identity(self):
        from bilqis_mlx.runtime.factory_task_authority import _source_view

        release, graph, sources, answers = episode_factory_release()
        context = __import__(
            "bilqis_mlx.runtime.source_execution", fromlist=["SourceExecutionContext"]
        ).SourceExecutionContext(release, graph, None, sources, answers)
        row = context.draw_rows(seed=17, capability=CAPABILITY, each=1)[0]
        capability = release.execution_plan.capability_map[CAPABILITY]
        lowerer = registered_episode_lowerer()
        goal, binding = lowerer.lower(
            _source_view(row), semantic_release="e" * 64, capability=capability)
        resolved = lowerer.resolve(
            row, semantic_release="e" * 64, capability=capability)

        self.assertEqual(goal.output_signature, "Number")
        self.assertTrue(all(node.operands[0] is None for node in goal.expression_or_holes.nodes
                            if node.node_id.startswith("select-")))
        self.assertEqual(len(binding.operands), 6)
        selected = tuple(
            node.operands[0].source_handle for node in resolved.expression_or_holes.nodes
            if node.node_id.startswith("select-"))
        self.assertTrue(selected)
        self.assertTrue(all(handle.startswith("source:c13:") for handle in selected))
        self.assertNotIn(str(row["gold"]), selected)

    def test_test_scoped_lowerer_registration_matches_exact_provider_digest(self):
        from bilqis_mlx.source_adapters import task_goal_registry

        lowerer = registered_episode_lowerer()
        with patch.object(
                task_goal_registry, "live_task_goal_lowerers",
                return_value=(*task_goal_registry.live_task_goal_lowerers(), lowerer)):
            selected = task_goal_registry.require_task_goal_lowerer(
                lowerer.provider_id, lowerer.provider_implementation_sha256)
        self.assertIs(selected, lowerer)


if __name__ == "__main__":
    unittest.main()
