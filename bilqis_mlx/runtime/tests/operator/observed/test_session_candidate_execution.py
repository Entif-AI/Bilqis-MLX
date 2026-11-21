from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch


class SessionCandidateExecutionTests(unittest.TestCase):
    def test_source_materialization_timer_starts_after_observer_begin_step(self):
        from bilqis_mlx.runtime.bamf_operator.session_parts.native_session import execute_horizon
        from bilqis_mlx.runtime.bamf_operator.session import _emit_progress, _invalid

        parent = NS(
            teacher_state={}, retained_state=NS(optimizer_step=7),
            optimizer_hyperparameters='hp')
        selection = NS(
            offer=NS(source_seed=1, capability_id='cap'),
            visit=NS(identity=NS(visit_id='v')))
        cache = NS(generation=1, accepted_manifest_sha256='a' * 64)
        transaction = NS(parent=NS(optimizer_step=7), update_steps=1)
        step = NS(transaction=transaction, realized_cost={})
        observer = NS(begin_step=lambda *_args: None, update=lambda **_fields: None)
        prefix = 'bilqis_mlx.runtime.bamf_operator.session_parts.native_session.'
        clock = iter((0.0, 0.0, 0.25, 0.25, 0.35, 0.35, 0.45, 0.45, 0.55))
        with patch(prefix + 'prepare_candidate_evidence_root'), patch(
                prefix + '_Capture'), patch(prefix + 'FactoryDeliveryObservation'), patch(
                prefix + 'execute_accepted_priority_candidate', return_value=step) as execute, patch(
                'bilqis_mlx.runtime.bamf_operator.session_parts.candidate_execution.time.perf_counter',
                side_effect=lambda: next(clock)):
            execute_horizon(
                Path('/tmp'), selection, NS(), parent, 'atlas', 'feature',
                ({'id': 'row'},), 1, cache, 1, None, 0, None, None, observer, None,
                emit_progress=_emit_progress, invalid=_invalid)

        kwargs = execute.call_args.kwargs
        self.assertAlmostEqual(kwargs['observer_begin_step_wall_seconds'], 0.25)
        self.assertAlmostEqual(kwargs['source_prepare_wall_seconds'], 0.10)
        self.assertAlmostEqual(kwargs['source_lesson_materialization_wall_seconds'], 0.10)

    def test_horizon_stops_after_real_motif_transition(self):
        from bilqis_mlx.runtime.bamf_operator.session_parts.native_session import execute_horizon
        from bilqis_mlx.runtime.bamf_operator.session import _emit_progress, _invalid
        events = []
        observer = NS(update=lambda **fields: events.append(fields))
        parent = NS(retained_state=NS(optimizer_step=7), optimizer_hyperparameters='hp')
        selection = NS(offer=NS(source_seed=1), visit=NS(identity=NS(visit_id='v')))
        transactions = [NS(parent=NS(optimizer_step=7), update_steps=1),
                        NS(parent=NS(optimizer_step=7), update_steps=2, motif_transition='stop')]
        prefix = 'bilqis_mlx.runtime.bamf_operator.session_parts.native_session.'
        cache = NS(generation=1, accepted_manifest_sha256='a' * 64)
        with patch(prefix + 'prepare_candidate_evidence_root'), patch(prefix + '_Capture'), patch(
                prefix + 'FactoryDeliveryObservation'), patch(
                prefix + 'execute_accepted_priority_candidate', side_effect=[NS(transaction=x) for x in transactions]) as execute:
            steps, _capture = execute_horizon(
                Path('/tmp'), selection, NS(), parent, 'atlas', 'feature',
                ({'id': 'row'},), 4, cache, 1, None, 0, None, None, observer, None,
                emit_progress=_emit_progress, invalid=_invalid)
        self.assertEqual(len(steps), 2)
        self.assertEqual(execute.call_count, 2)
        self.assertEqual(events, [{'candidate_step': 1, 'candidate_optimizer_step': 8},
                                  {'candidate_step': 2, 'candidate_optimizer_step': 9}])

    def test_horizon_uses_selected_teacher_projection_for_first_instruction(self):
        from bilqis_mlx.runtime.bamf_operator.session_parts.native_session import execute_horizon
        from bilqis_mlx.runtime.bamf_operator.session import _emit_progress, _invalid
        observer = NS(update=lambda **fields: None)
        parent = NS(
            teacher_state={"schema": "raw-genesis"},
            retained_state=NS(optimizer_step=0),
            optimizer_hyperparameters='hp',
        )
        selection = NS(
            offer=NS(source_seed=1, capability_id='cap:first'),
            visit=NS(
                identity=NS(visit_id='v'),
                projection=NS(teacher_state={"schema": "projected-c03"}),
            ),
        )
        cache = NS(generation=0, accepted_manifest_sha256='a' * 64)
        transaction = NS(parent=NS(optimizer_step=0), update_steps=1)
        step = NS(transaction=transaction, realized_cost={})
        prefix = 'bilqis_mlx.runtime.bamf_operator.session_parts.native_session.'
        with patch(prefix + 'prepare_candidate_evidence_root'), patch(
                prefix + '_Capture') as capture, patch(
                prefix + 'FactoryDeliveryObservation'), patch(
                prefix + 'execute_accepted_priority_candidate', return_value=step), patch(
                'bilqis_mlx.learning.teacher_lineage.instruction_history',
                return_value=('COMPLETE', ())) as history, patch(
                'bilqis_mlx.runtime.priority_rejection_replay.rejection_recency',
                return_value=(None, ())):
            execute_horizon(
                Path('/tmp'), selection, NS(), parent, 'atlas', 'feature',
                ({'id': 'row'},), 1, cache, 1, None, 0, None, None, observer, None,
                emit_progress=_emit_progress, invalid=_invalid)
        history.assert_called_once_with(selection.visit.projection.teacher_state)
        self.assertTrue(capture.call_args.kwargs['introductory'])

    def test_completed_step_projects_every_performance_field_without_authority_change(self):
        from bilqis_mlx.runtime.bamf_operator.performance import STEP_COST_FIELDS
        from bilqis_mlx.runtime.bamf_operator.session_parts.native_session import execute_horizon
        from bilqis_mlx.runtime.bamf_operator.session import _emit_progress, _invalid
        transaction = NS(parent=NS(optimizer_step=7), update_steps=1)
        cost = _complete_step_cost()
        events = []
        observer = NS(update=lambda **fields: events.append(fields))
        parent = NS(retained_state=NS(optimizer_step=7), optimizer_hyperparameters='hp')
        selection = NS(offer=NS(source_seed=1), visit=NS(identity=NS(visit_id='v')))
        cache = NS(generation=1, accepted_manifest_sha256='a' * 64)
        step = NS(transaction=transaction, realized_cost=cost)
        prefix = 'bilqis_mlx.runtime.bamf_operator.session_parts.native_session.'
        with patch(prefix + 'prepare_candidate_evidence_root'), patch(prefix + '_Capture'), patch(
                prefix + 'FactoryDeliveryObservation'), patch(
                prefix + 'execute_accepted_priority_candidate', return_value=step):
            steps, _capture = execute_horizon(
                Path('/tmp'), selection, NS(), parent, 'atlas', 'feature',
                ({'id': 'row'},), 1, cache, 1, None, 0, None, None, observer, None,
                emit_progress=_emit_progress, invalid=_invalid)
        self.assertIs(steps[0].transaction, transaction)
        self.assertEqual(events[0]['candidate_step'], 1)
        self.assertEqual(events[0]['candidate_optimizer_step'], 8)
        self.assertEqual(
            {name: events[0][name] for name in STEP_COST_FIELDS}, cost)


def _complete_step_cost():
    from bilqis_mlx.runtime.bamf_operator.performance import STEP_COST_FIELDS
    cost = {name: 0.0 for name in STEP_COST_FIELDS}
    cost.update({
        'candidate_step_wall_seconds': 1.2,
        'candidate_unattributed_wall_seconds': 0.09,
        'pre_neural_source_compile_wall_seconds': 0.1,
        'currentness_binding_wall_seconds': 0.2,
        'b11_preflight_wall_seconds': 0.3,
        'b11_finite_validation_wall_seconds': 0.01,
        'b11_execution_rebinding_wall_seconds': 0.01,
        'b11_refinement_selection_wall_seconds': 0.01,
        'b11_route_compatibility_wall_seconds': 0.01,
        'b11_route_kernel_prepare_wall_seconds': 0.01,
        'b11_preflight_other_wall_seconds': 0.25,
        'b11_autodiff_wall_seconds': 0.4,
        'b11_autodiff_dispatch_wall_seconds': 0.01,
        'b11_autodiff_dispatch_rebind_wall_seconds': 0.001,
        'b11_autodiff_dispatch_source_producer_wall_seconds': 0.002,
        'b11_autodiff_dispatch_source_hidden_graph_wall_seconds': 0.002,
        'b11_autodiff_dispatch_refinement_graph_wall_seconds': 0.001,
        'b11_autodiff_dispatch_route_graph_wall_seconds': 0.001,
        'b11_autodiff_dispatch_transform_other_wall_seconds': 0.003,
        'b11_autodiff_materialization_wall_seconds': 0.34,
        'b11_route_evidence_wall_seconds': 0.04,
        'b11_autodiff_other_wall_seconds': 0.01,
        'b11_gradient_finite_validation_wall_seconds': 0.02,
        'b11_postflight_validation_wall_seconds': 0.03,
        'b11_postflight_trajectory_validation_wall_seconds': 0.005,
        'b11_postflight_output_attestation_wall_seconds': 0.01,
        'b11_postflight_loss_validation_wall_seconds': 0.005,
        'b11_postflight_gradient_structure_wall_seconds': 0.005,
        'b11_postflight_result_construction_wall_seconds': 0.005,
        'b11_total_wall_seconds': 0.75,
        'optimizer_admission_wall_seconds': 0.1,
        'evidence_capture_wall_seconds': 0.01,
        'c08_gradient_launches': 1,
        'c08_vectorized_microbatches': 1,
        'c08_materialization_barriers': 1,
        'c08_logical_batch_wall_seconds': 0.7,
        'c08_row_execution_inputs_wall_seconds': 0.08,
        'c08_group_execution_wall_seconds': 0.6,
        'c08_aggregation_wall_seconds': 0.04,
        'c08_result_construction_wall_seconds': 0.01,
        'c08_unattributed_wall_seconds': 0.06,
        'c08_reused_materialized_full_batch': True,
        'c08_rows_per_gradient_launch': 4.0,
        'b11_provider_draw_count': 16,
        'b11_atlas_reload_count': 4,
        'logical_rows': 4,
        'compiled_positions': 32,
    })
    return cost


if __name__ == '__main__':
    unittest.main()
