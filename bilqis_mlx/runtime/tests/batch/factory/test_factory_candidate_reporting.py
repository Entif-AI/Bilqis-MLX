"""B11.2 compact Factory reporting boundary."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_model import BamfGradientExecution
from bilqis_mlx.runtime.candidate import execution as candidate_execution
from bilqis_mlx.runtime.candidate import step as candidate_step
from bilqis_mlx.runtime.factory_candidate_training import (
    FactoryCandidateDiagnostics,
    _realized_candidate_cost,
    _reporting_diagnostics,
)


def _reporting_fixture():
    compiled = lambda positions: SimpleNamespace(
        source_execution_authority=object(),
        compiled=SimpleNamespace(
            compiled=SimpleNamespace(rows=(SimpleNamespace(positions=positions),)))
    )
    prepared = SimpleNamespace(compiled_rows=(
        compiled((1, 2, 3)), compiled((1, 2))))
    resource = SimpleNamespace(estimated_peak_bytes=128)
    budget = SimpleNamespace(allocation_bytes=256)
    transaction = SimpleNamespace(update_steps=2)
    feature_context = SimpleNamespace(
        atlas_reload_count=1, feature_manifest_rebuild_count=1,
        visit_atlas_reload_count=1, visit_feature_manifest_rebuild_count=1)
    gradient = SimpleNamespace(_performance_observation={
        "b11_preflight_wall_seconds": 0.2,
        "b11_finite_validation_wall_seconds": 0.01,
        "b11_execution_rebinding_wall_seconds": 0.02,
        "b11_refinement_selection_wall_seconds": 0.03,
        "b11_route_compatibility_wall_seconds": 0.04,
        "b11_route_kernel_prepare_wall_seconds": 0.05,
        "b11_fallback_trace_preflight_wall_seconds": 0.0,
        "b11_preflight_other_wall_seconds": 0.05,
        "b11_autodiff_wall_seconds": 0.4,
        "b11_autodiff_dispatch_wall_seconds": 0.03,
        "b11_autodiff_materialization_wall_seconds": 0.31,
        "b11_route_evidence_wall_seconds": 0.04,
        "b11_autodiff_other_wall_seconds": 0.02,
        "b11_gradient_finite_validation_wall_seconds": 0.06,
        "b11_postflight_validation_wall_seconds": 0.07,
        "c08_group_execution_wall_seconds": 0.7,
        "c08_row_execution_inputs_wall_seconds": 0.08,
        "c08_aggregation_wall_seconds": 0.05,
        "c08_final_materialization_wall_seconds": 0.04,
        "c08_result_construction_wall_seconds": 0.01,
        "c08_unattributed_wall_seconds": 0.01,
        "c08_reused_materialized_full_batch": True,
        "b11_provider_draw_count": 8,
        "b11_atlas_reload_count": 4,
    })
    stage = {
        "candidate_step_started_at": 0.75,
        "pre_neural_source_compile_wall_seconds": 0.1,
        "currentness_binding_wall_seconds": 0.3,
        "optimizer_admission_wall_seconds": 0.1,
        "motif_staging_wall_seconds": 0.0,
        "candidate_terminal_step": False,
    }
    return prepared, resource, budget, transaction, feature_context, gradient, stage


class FactoryCandidateReportingTests(unittest.TestCase):
    def test_learning_first_candidate_generation_does_not_bind_parent_cache(self):
        cache = object()
        candidate = SimpleNamespace(
            optimizer=SimpleNamespace(parameters={"candidate": object()}))
        parent = SimpleNamespace(topology=object(), extents=object())

        with patch(
                "bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode."
                "strict_evidence_enabled", return_value=False), patch.object(
                    candidate_step, "bind_execution_generation",
                    side_effect=AssertionError(
                        "speculative weights were bound to accepted cache")), patch.object(
                    candidate_step, "bind_learning_first_step_authority",
                            return_value="candidate-generation") as issue:
            bound, generation = candidate_step._candidate_cache_and_generation(
                "unused", object(), parent, candidate, None,
                accepted_cache=cache)

        self.assertIs(bound, cache)
        self.assertEqual(generation, "candidate-generation")
        issue.assert_called_once_with(cache, parent, candidate, unittest.mock.ANY)

    def test_strict_candidate_generation_keeps_exact_execution_binding(self):
        cache = SimpleNamespace(generation_binding="strict-generation")
        candidate = SimpleNamespace(
            optimizer=SimpleNamespace(parameters={"candidate": object()}))
        parent = SimpleNamespace(topology=object(), extents=object())
        candidate_cache = SimpleNamespace(generation_binding="strict-generation")
        binding = SimpleNamespace(generation_digest="strict-generation")
        currentness = object()
        current = SimpleNamespace(_cache=cache)

        with patch(
                "bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode."
                "strict_evidence_enabled", return_value=True), patch.object(
                    candidate_step, "bind_candidate_execution_cache",
                    return_value=candidate_cache), patch.object(
                        candidate_step, "bind_execution_generation",
                        return_value=binding) as exact, patch.object(
                            candidate_step, "issue_learning_first_step_authority",
                            side_effect=AssertionError("strict path used cheap token")), patch(
                                "bilqis_mlx.runtime.bamf_bundle.currentness_transaction."
                                "require_accepted_currentness",
                                return_value=current):
            bound, generation = candidate_step._candidate_cache_and_generation(
                "unused", object(), parent, candidate, currentness,
                accepted_cache=cache)

        self.assertIs(bound, candidate_cache)
        self.assertEqual(generation, "strict-generation")
        exact.assert_called_once()

    def test_learning_first_neural_execution_does_not_receive_parent_cache(self):
        cache = object()
        parent = SimpleNamespace(
            retained_state=SimpleNamespace(
                optimizer=SimpleNamespace(parameters={"parent": object()})))
        prepared = SimpleNamespace(compiled_rows=(object(),))
        feature_context = SimpleNamespace(snapshot=object())
        gradient = SimpleNamespace(loss_total=object())
        execute_row = Mock(return_value=(gradient, object(), object()))
        admit = Mock(return_value="candidate")

        with patch(
                "bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode."
                "strict_evidence_enabled", return_value=False), patch.object(
                    candidate_execution, "execute_factory_training_row",
                    execute_row), patch.object(
                        candidate_execution, "_learning_first_admit", admit):
            result = candidate_execution._execute_training_and_admission(
                "unused", object(), parent, prepared, feature_context,
                "candidate-generation", cache, object(), object(), 1.0, None,
                None, None, None, None, None)

        self.assertIsNone(execute_row.call_args.args[5])
        self.assertIs(admit.call_args.args[1], cache)
        self.assertEqual(result[3], "candidate")

    def test_heavy_gradient_execution_is_retained_only_by_explicit_opt_in(self):
        execution = object.__new__(BamfGradientExecution)

        self.assertIsNone(_reporting_diagnostics(execution, False))

        diagnostics = _reporting_diagnostics(execution, True)
        self.assertIs(type(diagnostics), FactoryCandidateDiagnostics)
        self.assertIs(diagnostics.gradient_execution, execution)
        self.assertEqual(
            diagnostics.schema_version,
            "bilqis.mlx.b11-factory-diagnostics/v1")

        with self.assertRaises(BilqisError):
            _reporting_diagnostics(execution, 1)

    def test_realized_cost_projects_stage_and_b11_observation_without_device_work(self):
        (prepared, resource, budget, transaction, feature_context,
         gradient, stage) = _reporting_fixture()
        loss = SimpleNamespace(item=lambda: 1.5)
        with patch(
                "bilqis_mlx.runtime.factory_candidate_training.time.perf_counter",
                return_value=2.0):
            cost = _realized_candidate_cost(
                1.0, 0.75, loss, prepared, resource, budget, transaction,
                feature_context, True, (2, 1, 1, 0, 0.8), stage, gradient)
        self.assertEqual(cost["candidate_step_wall_seconds"], 1.25)
        self.assertEqual(cost["b11_preflight_wall_seconds"], 0.2)
        self.assertEqual(cost["b11_refinement_selection_wall_seconds"], 0.03)
        self.assertEqual(cost["b11_route_kernel_prepare_wall_seconds"], 0.05)
        self.assertEqual(cost["b11_preflight_other_wall_seconds"], 0.05)
        self.assertEqual(cost["b11_autodiff_wall_seconds"], 0.4)
        self.assertEqual(cost["b11_autodiff_materialization_wall_seconds"], 0.31)
        self.assertEqual(cost["b11_gradient_finite_validation_wall_seconds"], 0.06)
        self.assertEqual(cost["b11_postflight_validation_wall_seconds"], 0.07)
        self.assertEqual(cost["b11_provider_draw_count"], 8)
        self.assertEqual(cost["b11_atlas_reload_count"], 4)
        self.assertEqual(cost["b11_source_authority_bound_rows"], 2)
        self.assertEqual(cost["b11_source_cold_requalification_rows"], 0)
        self.assertEqual(cost["c08_gradient_launches"], 2)
        self.assertEqual(cost["c08_vectorized_microbatches"], 1)
        self.assertEqual(cost["c08_group_execution_wall_seconds"], 0.7)
        self.assertEqual(cost["c08_row_execution_inputs_wall_seconds"], 0.08)
        self.assertEqual(cost["c08_final_materialization_wall_seconds"], 0.04)
        self.assertTrue(cost["c08_reused_materialized_full_batch"])
        self.assertEqual(cost["logical_rows"], 2)
        self.assertEqual(cost["compiled_positions"], 5)
        self.assertFalse(cost["candidate_terminal_step"])

        terminal_stage = {
            **stage,
            "motif_staging_wall_seconds": 0.3,
            "candidate_terminal_step": True,
        }
        with patch(
                "bilqis_mlx.runtime.factory_candidate_training.time.perf_counter",
                return_value=2.0):
            terminal = _realized_candidate_cost(
                1.0, 0.75, loss, prepared, resource, budget, transaction,
                feature_context, True, (2, 1, 1, 0, 0.8),
                terminal_stage, gradient)
        self.assertTrue(terminal["candidate_terminal_step"])
        self.assertEqual(terminal["motif_staging_wall_seconds"], 0.3)
