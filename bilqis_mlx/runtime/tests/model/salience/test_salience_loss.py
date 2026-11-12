"""Literal five-class loss and absent-versus-UNKNOWN MLX gradients."""
from bilqis_mlx.runtime.salience_loss import salience_loss_components

import math
import unittest
import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2


class SalienceLossTests(unittest.TestCase):
    def setUp(self):
        self.topology = ModelTopologySpecV2()
        self.extents = GenerationExtents(1, 1, 'a' * 64, 'b' * 64, 'c' * 64)
        self.hidden = mx.ones((self.topology.width,), dtype=mx.float32)
        self.parameters = {}
        for name in ('impact', 'exigency', 'novelty'):
            self.parameters['readout.salience.' + name] = mx.zeros((5, self.topology.width))
            self.parameters['readout.salience_bias.' + name] = mx.zeros((5,))

    def components(self, parameters, labels):
        return salience_loss_components(parameters, self.hidden, self.topology, self.extents, labels)

    def test_each_present_head_is_point_zero_five_cross_entropy(self):
        parts = self.components(self.parameters, {'impact': 2, 'exigency': 4})
        expected = .05 * math.log(5)
        self.assertAlmostEqual(float(parts.impact), expected, places=6)
        self.assertAlmostEqual(float(parts.exigency), expected, places=6)
        self.assertEqual(float(parts.novelty), 0.)
        self.assertAlmostEqual(float(parts.total), 2 * expected, places=6)
        self.assertEqual(parts.heads, ('impact', 'exigency'))

    def test_absent_head_has_zero_gradient_and_explicit_unknown_is_supervised(self):
        for labels in ({}, {'impact': 2}, {'novelty': 0}):
            gradient = mx.grad(lambda parameters: self.components(parameters, labels).total)(self.parameters)
            for name in ('impact', 'exigency', 'novelty'):
                bias = gradient['readout.salience_bias.' + name]
                if name not in labels:
                    self.assertEqual(tuple(bias.tolist()), (0.,) * 5)
                else:
                    target = labels[name]
                    for index, actual in enumerate(bias.tolist()):
                        self.assertAlmostEqual(actual, -.04 if index == target else .01, places=6)
                    self.assertGreater(float(mx.abs(gradient['readout.salience.' + name]).sum()), 0.)

    def test_unknown_values_and_nonordinal_labels_fail(self):
        for labels in ({'novelty': -1}, {'impact': 5}, {'impact': True}, {'truth': 2}):
            with self.assertRaises(BilqisError):
                self.components(self.parameters, labels)
