"""Structural test shard from test_atlas_training_adapter.py; assertions preserved."""
from dataclasses import dataclass, replace
import unittest
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.adapters import SourceAdapterRegistry
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.factory.tests.test_teaching import closed_source_fixture
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.runtime.atlas_training_adapter import BamfTarget, compile_training_batch, require_current_release
from bilqis_mlx.semantics.core import Literal
from bilqis_mlx.runtime.tests.batch.test_atlas_training_adapter_helpers import AtlasTrainingAdapterFixture

class AtlasAdapterExecutionTest(AtlasTrainingAdapterFixture):
        def test_padding_uses_actual_maximum_and_c08_partition(self):
            from bilqis_mlx.runtime.atlas_training_adapter import pad_microbatches
            batch = self.compile(self.context.draw_rows(seed=17, capability='Z.C0', each=2))
            groups = pad_microbatches(batch, {}, 100, plan_microbatches=lambda rows, topology, budget: ((0, 1),),
                indices_for_plan=lambda plan: plan,
                positions_for=lambda prefix: tuple(int(x) for x in prefix.ast.value.split(',')))
            self.assertEqual(groups[0].positions, ((1, 2, None), (1, 2, 1)))
            self.assertEqual(groups[0].padding_mask, ((True, True, False), (True, True, True)))
            with self.assertRaises(BilqisError):
                pad_microbatches(batch, {}, 100, plan_microbatches=lambda *args: ((0,),),
                    indices_for_plan=lambda plan: plan, positions_for=lambda prefix: (1,))

        def test_padding_reserves_answer_decision_budget(self):
            from bilqis_mlx.runtime.atlas_training_adapter import pad_microbatches
            with self.assertRaises(BilqisError):
                pad_microbatches(self.compile(self.rows), {}, 100,
                    plan_microbatches=lambda *args: ((0,),), indices_for_plan=lambda plan: plan,
                    positions_for=lambda prefix: (1,) * 1024)

        def test_auxiliaries_require_evidence_and_stay_out_of_input(self):
            from bilqis_mlx.runtime.atlas_training_adapter import attach_auxiliaries
            batch = self.compile(self.rows)
            self.assertEqual(attach_auxiliaries(batch, {}, verify=lambda *args: False), batch)
            with self.assertRaises(BilqisError):
                attach_auxiliaries(batch, {self.rows[0]['id']: {'role': ('subject', 'SOURCE', 'receipt')}},
                                   verify=lambda *args: False)
            result = attach_auxiliaries(batch, {self.rows[0]['id']: {'role': ('subject', 'SOURCE', 'receipt')}},
                                        verify=lambda *args: True)
            self.assertEqual(result.rows[0].model_input, batch.rows[0].model_input)
            self.assertEqual(result.rows[0].auxiliaries, (('role', 'subject', 'SOURCE', 'receipt'),))

        def test_real_observation_capture_preserves_rows_and_cost(self):
            import tempfile
            from bilqis_mlx.runtime.atlas_training_adapter import capture_realized_delivery
            from bilqis_mlx.runtime.teacher_observation_capture import ObservationCapture, read_sidecar, store_sidecar, read_observation
            batch = self.compile(self.rows)
            with tempfile.TemporaryDirectory() as root:
                capture = ObservationCapture(root, {})
                capture.attempt_id = 'fixture-attempt'
                proposal_ref = store_sidecar(root, {'attempt_id': capture.attempt_id})
                capture.proposal_id = proposal_ref['sha256']
                capture.select_option('Z.C0', None)
                capture_realized_delivery(batch, self.context, capture, 'Z.C0', 1, self.rows,
                    generation_binding=batch.generation_binding, option_rows=self.rows, priority=(),
                    preservation=(), support=(), enrichment=(), guidance=None, controls={}, seed=42,
                    cost={'wall_seconds': 0.25})
                payload = read_sidecar(root, capture.steps[0])
                self.assertEqual(payload['controls']['realized_cost'], {'wall_seconds': 0.25})
                self.assertEqual(read_sidecar(root, payload['positions'][0]['row']), self.rows[0])
                envelope = store_sidecar(root, {'attempt_id': capture.attempt_id, 'proposal_id': capture.proposal_id,
                    'proposal': proposal_ref, 'steps': capture.steps})
                observed = read_observation(root, {'teacher_observation': {'attempt_id': capture.attempt_id,
                    'proposal_id': capture.proposal_id, 'envelope': envelope}})
                self.assertEqual(observed['steps'][0]['positions'][0]['row'], self.rows[0])
                self.assertEqual(observed['steps'][0]['controls']['realized_cost'], {'wall_seconds': 0.25})
                with self.assertRaises(BilqisError):
                    capture_realized_delivery(batch, self.context, capture, 'Z.C0', 1,
                        [{**self.rows[0], 'gold': 'TRUE'}], generation_binding=batch.generation_binding,
                        option_rows=self.rows, priority=(), preservation=(), support=(), enrichment=(),
                        guidance=None, controls={}, seed=42, cost={'wall_seconds': 0.25})

        def test_training_and_inference_use_one_selector_without_inference_targets(self):
            from bilqis_mlx.runtime.atlas_training_adapter import execute_with_backend
            batch = self.compile(self.rows)
            selector = lambda topology: ('backend', topology['identity'])
            invoke = lambda backend, inputs, targets: (backend, inputs, targets)
            kwargs = dict(generation_binding=batch.generation_binding, model_backend=selector, invoke=invoke)
            prediction = execute_with_backend(batch, self.context, {'identity': 'fixture'}, training=False, **kwargs)
            training = execute_with_backend(batch, self.context, {'identity': 'fixture'}, training=True, **kwargs)
            self.assertEqual(prediction[:2], training[:2])
            self.assertIsNone(prediction[2])
            self.assertEqual(training[2][0][0], batch.rows[0].target)
