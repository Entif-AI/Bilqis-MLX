"""Visit-currentness guards for the neural-inert production journey."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.runtime.accepted_priority_visit import accepted_priority_school
from bilqis_mlx.runtime.bamf_operator.session import _execution_context
from bilqis_mlx.runtime.foundation_teacher_owner import select_foundation_priority_visit

from .pre_neural_journey_support import (
    PreNeuralJourneySupport, historical_school_release, journey_source,
    portable_atlas_snapshot, wide_shape_patch,
)


class PreNeuralJourneyCurrentnessTests(PreNeuralJourneySupport, unittest.TestCase):
    def test_priority_planning_authenticates_generation_once_for_all_capabilities(self):
        from bilqis_mlx.runtime import priority_planning_generation

        original = priority_planning_generation._current_cache
        calls = 0

        def counted(*args, **kwargs):
            nonlocal calls
            calls += 1
            return original(*args, **kwargs)

        with patch.object(priority_planning_generation, "_current_cache", side_effect=counted):
            (_pointer, _before, _after, context, selected, _rows,
             _pointer_bytes, _event_bytes) = self.exercise_journey()

        self.assertEqual(len(context.release.execution_plan.capabilities), 21)
        self.assertEqual(selected.status, "TEACHER_SELECTED")
        self.assertEqual(calls, 1)

    def test_21_capability_16_step_currentness_cost_is_bounded(self):
        from bilqis_mlx.runtime.bamf_bundle.currentness_transaction import (
            VisitCurrentnessMetrics, currentness_metrics,
            refresh_accepted_currentness,
        )

        self.current, self.parent_graph = historical_school_release()
        snapshot = portable_atlas_snapshot()
        schema, features, atlas_selection = journey_source(snapshot)
        metrics = VisitCurrentnessMetrics()
        with wide_shape_patch(len(snapshot.abi_entries)):
            self.publish_matching_genesis(snapshot, schema, features)
            with self.journey_mounts(snapshot, schema, features, atlas_selection):
                parent, context, atlas_path, _feature_path = _execution_context(
                    self.run, currentness_metrics=metrics)
                program = schedule_program_from_executable_release(context.release)
                cache = context._accepted_runtime_host._accepted_cache
                school = accepted_priority_school(
                    parent, program,
                    candidate_identity_sha256=cache._candidate_identity_sha256)
                selected = select_foundation_priority_visit(
                    self.run, context, atlas_path, program=program, school=school)
                transaction = selected.offer._planning_generation._accepted_currentness
                for _ in range(16):
                    refresh_accepted_currentness(transaction, transaction._parent)

        self.assertEqual(len(context.release.execution_plan.capabilities), 21)
        self.assertEqual(selected.status, "TEACHER_SELECTED")
        self.assertEqual(currentness_metrics(transaction), {
            "deep_authentication_count": 1,
            "accepted_cache_currentness_count": 16,
            "full_candidate_identity_hashes": 1,
            "bundle_tree_scans": 2,
        })

    def test_step_currentness_witness_skips_full_checkpoint_rehash_in_bound_frontier(self):
        from bilqis_mlx.runtime.bamf_bundle.currentness_transaction import (
            refresh_accepted_currentness,
        )
        from bilqis_mlx.runtime.lawful_teaching_frontier import (
            require_bound_lawful_teaching_frontier,
        )

        (_pointer, _before, _after, context, selected, _rows,
         _pointer_bytes, _event_bytes) = self.exercise_journey()
        planning = selected.offer._planning_generation
        parent = planning._parent
        transaction = planning._accepted_currentness
        from bilqis_mlx.runtime.bamf_bundle.source_authority_custody import currentness
        with patch.object(
                currentness, "_trust_root_snapshot",
                return_value=transaction._source_currentness._trust_root):
            step_currentness = refresh_accepted_currentness(transaction, parent)
        frontier = selected._lawful_frontier
        active_grade = SimpleNamespace(
            activation_sha256=frontier.active_grade_activation_sha256,
            definition=SimpleNamespace(
                definition_sha256=frontier.active_grade_definition_sha256,
                members=tuple(SimpleNamespace(capability_id=capability_id,
                                              semantic_id=semantic_id)
                              for capability_id, semantic_id
                              in frontier.active_grade_members),
            ),
        )

        with patch.object(
                currentness, "_trust_root_snapshot",
                return_value=transaction._source_currentness._trust_root), patch(
                "bilqis_mlx.runtime.active_generated_grade.read_active_generated_grade",
                return_value=active_grade), patch(
                "bilqis_mlx.runtime.active_generated_grade."
                "_read_bound_active_generated_grade",
                return_value=active_grade), patch(
                "bilqis_mlx.runtime.atlas_flywheel_runtime._accepted_checkpoint",
                side_effect=AssertionError("accepted checkpoint rehashed in hot step")):
            current = require_bound_lawful_teaching_frontier(
                frontier, context, parent,
                currentness_step=step_currentness)
        self.assertIs(current, frontier)

    def test_step_currentness_witness_is_revoked_by_next_refresh(self):
        from bilqis_mlx.runtime.bamf_bundle.currentness_transaction import (
            refresh_accepted_currentness,
            require_accepted_currentness_step,
        )

        (_pointer, _before, _after, _context, selected, _rows,
         _pointer_bytes, _event_bytes) = self.exercise_journey()
        planning = selected.offer._planning_generation
        parent = planning._parent
        transaction = planning._accepted_currentness
        from bilqis_mlx.runtime.bamf_bundle.source_authority_custody import currentness
        with patch.object(
                currentness, "_trust_root_snapshot",
                return_value=transaction._source_currentness._trust_root):
            first = refresh_accepted_currentness(transaction, parent)
            second = refresh_accepted_currentness(transaction, parent)

        with patch.object(
                currentness, "_trust_root_snapshot",
                return_value=transaction._source_currentness._trust_root):
            with self.assertRaises(ValueError):
                require_accepted_currentness_step(first, transaction, parent)
            self.assertIs(
                require_accepted_currentness_step(second, transaction, parent),
                second,
            )

    def test_step_currentness_live_fence_rechecks_mutable_authority_edges(self):
        from bilqis_mlx.runtime.bamf_bundle import bundle_currentness
        from bilqis_mlx.runtime.bamf_bundle import currentness_transaction
        from bilqis_mlx.runtime.bamf_bundle.currentness_transaction import (
            refresh_accepted_currentness,
            require_live_accepted_currentness_step,
        )
        from bilqis_mlx.runtime.bamf_bundle.source_authority_custody import currentness

        (_pointer, _before, _after, _context, selected, _rows,
         _pointer_bytes, _event_bytes) = self.exercise_journey()
        planning = selected.offer._planning_generation
        parent = planning._parent
        transaction = planning._accepted_currentness
        stable_trust_root = transaction._source_currentness._trust_root
        with patch.object(
                currentness, "_trust_root_snapshot",
                return_value=stable_trust_root):
            step = refresh_accepted_currentness(transaction, parent)

        with patch.object(
                currentness_transaction, "_pointer_snapshot",
                return_value=("9" * 64, transaction._acceptance_sha256,
                              transaction._acceptance_identity)), patch.object(
                    currentness, "_trust_root_snapshot",
                    return_value=stable_trust_root):
            with self.assertRaises(ValueError):
                require_live_accepted_currentness_step(step, transaction, parent)

        with patch.object(
                bundle_currentness, "_stat_identity",
                return_value=(9, 9, 9, 9, 9)), patch.object(
                    currentness, "_trust_root_snapshot",
                    return_value=stable_trust_root):
            with self.assertRaises(ValueError):
                require_live_accepted_currentness_step(step, transaction, parent)

        with patch.object(
                currentness, "_trust_root_snapshot",
                return_value=("HOST_SYSTEM_V1", 9, 9, 9, 9, 9)):
            with self.assertRaises(ValueError):
                require_live_accepted_currentness_step(step, transaction, parent)

        with patch.object(
                currentness_transaction, "contract_digest",
                return_value="9" * 64), patch.object(
                    currentness, "_trust_root_snapshot",
                    return_value=stable_trust_root):
            with self.assertRaises(ValueError):
                require_live_accepted_currentness_step(step, transaction, parent)

if __name__ == "__main__":
    unittest.main()
