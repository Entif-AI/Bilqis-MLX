"""Identity-reuse guards for the neural-inert production journey."""
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


class PreNeuralJourneyIdentityReuseTests(PreNeuralJourneySupport, unittest.TestCase):
    def test_ordinary_teacher_offer_binds_actual_previsit_diagnostic_context(self):
        from bilqis_mlx.learning.teacher_lineage import restore_teacher_lineage
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
            evidence_mode,
        )
        from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation

        self.current, self.parent_graph = historical_school_release()
        snapshot = portable_atlas_snapshot()
        schema, features, atlas_selection = journey_source(snapshot)
        with wide_shape_patch(len(snapshot.abi_entries)):
            self.publish_matching_genesis(snapshot, schema, features)
            pointer = (self.run / "bamf-state.json").read_bytes()
            events = (self.run / "events.jsonl").read_bytes()
            with self.journey_mounts(
                    snapshot, schema, features, atlas_selection,
                    patch_active_generated_grade=False), evidence_mode(strict=False):
                parent, context, atlas_path, _ = _execution_context(self.run)
                program = schedule_program_from_executable_release(context.release)
                selected = select_foundation_priority_visit(
                    self.run, context, atlas_path, program=program,
                    school=accepted_priority_school(parent, program))
            after = load_accepted_generation(self.run)

        self.assertEqual(selected.status, "TEACHER_SELECTED")
        how = selected.metadata["how_context"]
        self.assertEqual(how["diagnostics"]["native_previsit"], {
            "fixed_reference_deficit": None,
            "target_sample_deficit": None,
            "reference_conflict": False,
            "structural_debt": None,
        })
        teacher = restore_teacher_lineage(
            selected.visit.projection.teacher_state).teacher()
        key = selected.metadata["diagnostic_context_key"]
        self.assertEqual(how["diagnostic_context_key"], key)
        self.assertEqual(
            teacher["causal_experiment"]["diagnostic_contexts"][key],
            how["diagnostics"])
        self.assertEqual(after.retained_state.optimizer_step, 0)
        self.assertEqual((self.run / "bamf-state.json").read_bytes(), pointer)
        self.assertEqual((self.run / "events.jsonl").read_bytes(), events)

    def test_bound_accepted_parent_identity_is_reused_across_priority_hot_path(self):
        from bilqis_mlx.learning._atlas_candidate.identity_binding import (
            _reset_candidate_identity_metrics_for_tests,
            candidate_identity_metrics_snapshot,
        )

        self.current, self.parent_graph = historical_school_release()
        snapshot = portable_atlas_snapshot()
        schema, features, atlas_selection = journey_source(snapshot)
        with wide_shape_patch(len(snapshot.abi_entries)):
            self.publish_matching_genesis(snapshot, schema, features)
            with self.journey_mounts(snapshot, schema, features, atlas_selection):
                parent, context, atlas_path, _feature_path = _execution_context(self.run)
                program = schedule_program_from_executable_release(context.release)
                _reset_candidate_identity_metrics_for_tests()
                school = accepted_priority_school(parent, program)
                selected = select_foundation_priority_visit(
                    self.run, context, atlas_path, program=program, school=school)
                from bilqis_mlx.runtime.accepted_priority_candidate import (
                    _candidate_currentness,
                )
                _candidate_currentness(selected, context, None)
                from bilqis_mlx.runtime.accepted_teacher_custody import (
                    derive_c03_successor_bundle,
                )
                from bilqis_mlx.learning._atlas_candidate.identity_binding import (
                    bind_candidate_identity_or_fallback,
                )
                from dataclasses import replace
                parent_metrics = candidate_identity_metrics_snapshot()
                retained = replace(
                    parent.retained_state,
                    optimizer_step=parent.retained_state.optimizer_step + 1)
                bind_candidate_identity_or_fallback(
                    retained, parent.topology.digest, parent.extents.digest)
                candidate_bound_metrics = candidate_identity_metrics_snapshot()
                successor = derive_c03_successor_bundle(
                    self.run, retained, selected.visit,
                    next_seed=selected.visit.identity.selection_seed + 1,
                    cursor="identity-reuse-regression",
                    delivery_events=({
                        "event": "BAMF_IDENTITY_REUSE_REGRESSION",
                        "optimizer_step": retained.optimizer_step,
                    },),
                )
                metrics = candidate_identity_metrics_snapshot()

        self.assertEqual(selected.status, "TEACHER_SELECTED")
        self.assertEqual(successor.generation, parent.generation + 1)
        self.assertEqual(parent_metrics["candidate_identity_full_computations"], 0)
        self.assertEqual(parent_metrics["candidate_identity_numerical_bytes_hashed"], 0)
        self.assertEqual(
            candidate_bound_metrics["candidate_identity_full_computations"], 1)
        self.assertGreater(
            candidate_bound_metrics["candidate_identity_numerical_bytes_hashed"], 0)
        self.assertEqual(
            metrics["candidate_identity_full_computations"],
            candidate_bound_metrics["candidate_identity_full_computations"])
        self.assertEqual(
            metrics["candidate_identity_numerical_bytes_hashed"],
            candidate_bound_metrics["candidate_identity_numerical_bytes_hashed"])
        self.assertGreater(
            metrics["candidate_identity_require_calls"],
            candidate_bound_metrics["candidate_identity_require_calls"])

    def test_priority_planning_reuses_generation_binding_after_context_authentication(self):
        from bilqis_mlx.runtime import backbone_identity
        from bilqis_mlx.runtime.bamf_bundle import accepted_execution_runtime

        self.current, self.parent_graph = historical_school_release()
        snapshot = portable_atlas_snapshot()
        schema, features, atlas_selection = journey_source(snapshot)
        original = backbone_identity.execution_generation_digest
        calls = 0

        def counted(*args, **kwargs):
            nonlocal calls
            calls += 1
            return original(*args, **kwargs)

        with wide_shape_patch(len(snapshot.abi_entries)):
            self.publish_matching_genesis(snapshot, schema, features)
            with self.journey_mounts(snapshot, schema, features, atlas_selection):
                parent, context, atlas_path, _feature_path = _execution_context(self.run)
                program = schedule_program_from_executable_release(context.release)
                school = accepted_priority_school(parent, program)
                with patch.object(
                        backbone_identity, "execution_generation_digest",
                        side_effect=counted), patch.object(
                            accepted_execution_runtime, "execution_generation_digest",
                            side_effect=counted):
                    selected = select_foundation_priority_visit(
                        self.run, context, atlas_path, program=program, school=school)

        self.assertEqual(len(context.release.execution_plan.capabilities), 21)
        self.assertEqual(selected.status, "TEACHER_SELECTED")
        # #1173 owns one execution-generation proof per immutable state. Once the
        # accepted execution context has bound it, C03 planning must not hash the
        # parameter tree again during the 21-capability fan-out.
        self.assertEqual(calls, 0)



if __name__ == "__main__":
    unittest.main()
