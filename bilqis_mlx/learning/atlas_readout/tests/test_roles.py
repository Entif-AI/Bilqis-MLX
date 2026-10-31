"""ROLE uses released schema coordinates and the shared factor table."""
from dataclasses import replace
import unittest
import mlx.core as mx
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_readout.roles import compile_frame_output, role_logits
from bilqis_mlx.learning.atlas_readout.tests.helpers import frame_release, role_parameters


class RoleHeadTests(unittest.TestCase):
    def setUp(self):
        mx.set_default_device(mx.cpu)
        self.schema, self.released, self.features = frame_release()
        self.domain = compile_frame_output(self.schema, self.released, self.features)
        self.parameters = role_parameters(self.features)
        self.hidden = mx.zeros((768,), dtype=mx.float32).at[0].add(3).at[1].add(1)

    def output(self, occurrence=0, **kwargs):
        return role_logits(self.hidden, self.domain, occurrence,
                           kwargs.get('parameters', self.parameters),
                           kwargs.get('features', self.features))

    def test_role_and_occurrence_are_exact_coordinates(self):
        output = self.output()
        self.assertEqual(output.logits.tolist(), [3., 1.])
        self.assertEqual(tuple((c.role_id, c.occurrence_index) for c in output.candidates),
                         (('agent', 0), ('theme', 0)))
        self.assertEqual(output.candidates[0].schema_id, self.schema.schema_id)
        self.assertEqual(output.candidates[0].revision, 1)
        repeated = self.output(1)
        self.assertEqual([(c.role_id, c.occurrence_index) for c in repeated.candidates], [('theme', 1)])
        self.assertEqual(repeated.logits.tolist(), [1.])
        self.assertEqual(self.domain.modality_id, 'answer.structured-frame/v1')
        self.assertEqual(output.modality_id, 'answer.role-selection/v1')

    def test_swap_shared_role_rows_swaps_role_logits(self):
        params = dict(self.parameters)
        table = params['features.role']
        a, b = [dict(self.features.role_map)[r] for r in ('agent', 'theme')]
        params['features.role'] = table.at[a].add(table[b] - table[a]).at[b].add(table[a] - table[b])
        params['readout.control'] = mx.full((4, 768), 1e6)
        self.assertEqual(self.output(parameters=params).logits.tolist(), [1., 3.])
        params['readout.control'] *= -1
        self.assertEqual(self.output(parameters=params).logits.tolist(), [1., 3.])

    def test_occurrence_boundaries_reject(self):
        for occurrence in (-1, 2, True, 1.5):
            with self.subTest(occurrence=occurrence), self.assertRaises(BilqisError):
                self.output(occurrence)

    def test_schema_body_and_release_changes_reject(self):
        with self.assertRaises(BilqisError):
            compile_frame_output(replace(self.schema, roles=self.schema.roles[::-1]), self.released, self.features)
        with self.assertRaises(BilqisError):
            compile_frame_output(self.schema, self.released, replace(self.features, semantic_release='d'*64))
        with self.assertRaises(BilqisError):
            self.output(features=replace(self.features, role_map=self.features.role_map[::-1]))

    def test_parameter_shapes_and_nonfinite_logits_reject(self):
        for tensor in (mx.zeros((128, 767)), mx.full((128, 768), float('nan'))):
            with self.assertRaises(BilqisError):
                self.output(parameters={**self.parameters, 'readout.role_query': tensor})

    def test_gradients_reach_shared_role_and_query(self):
        def loss(params):
            output = self.output(parameters=params)
            return mx.logsumexp(output.logits) - output.logits[1]
        gradient = mx.grad(loss)(self.parameters)
        for name in ('features.role', 'readout.role_query'):
            self.assertGreater(float(mx.sum(mx.abs(gradient[name]))), 0.)
            self.assertTrue(bool(mx.all(mx.isfinite(gradient[name]))))
