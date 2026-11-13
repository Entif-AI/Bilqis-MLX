"""CONTROL is the separate B01 four-action classifier."""
import unittest
import mlx.core as mx
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_readout.control import ControlAction, control_logits


class ControlTests(unittest.TestCase):
    def setUp(self):
        mx.set_default_device(mx.cpu)
        self.hidden = mx.zeros((768,), dtype=mx.float32).at[0].add(2)
        self.parameters = {'readout.control': mx.zeros((4, 768), dtype=mx.float32),
                           'readout.control_bias': mx.array([0., 1., 2., 3.])}

    def test_fixed_codes_and_end_mask(self):
        output = control_logits(self.hidden, self.parameters, 'a'*64, can_end=True)
        self.assertEqual(output.candidates, tuple(x.value for x in ControlAction))
        self.assertEqual(output.logits.tolist(), [0., 1., 2., 3.])
        masked = control_logits(self.hidden, self.parameters, 'a'*64, can_end=False)
        self.assertEqual(masked.candidates, output.candidates[:3])
        self.assertEqual(masked.logits.tolist(), [0., 1., 2.])

    def test_role_table_cannot_change_control(self):
        params = {**self.parameters, 'features.role': mx.full((512, 128), 99),
                  'readout.role_query': mx.full((128, 768), -9)}
        self.assertEqual(control_logits(self.hidden, params, 'a'*64, can_end=True).logits.tolist(),
                         [0., 1., 2., 3.])
        with self.assertRaises(ValueError):
            ControlAction('agent')

    def test_gradient_reaches_control_weights_and_bias(self):
        def loss(params):
            logits = control_logits(self.hidden, params, 'a'*64, can_end=True).logits
            return mx.logsumexp(logits) - logits[0]
        gradient = mx.grad(loss)(self.parameters)
        for name in self.parameters:
            self.assertTrue(bool(mx.all(mx.isfinite(gradient[name]))))
            self.assertGreater(float(mx.sum(mx.abs(gradient[name]))), 0)

    def test_bad_boundary_rejects(self):
        for params in ({**self.parameters, 'readout.control': mx.zeros((3, 768))},
                       {**self.parameters, 'readout.control_bias': mx.array([0., 1., 2., float('nan')])}):
            with self.assertRaises(BilqisError):
                control_logits(self.hidden, params, 'a'*64, can_end=True)
