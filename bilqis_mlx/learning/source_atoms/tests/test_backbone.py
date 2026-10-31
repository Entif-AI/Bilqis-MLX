"""Real A05/A01 source ingress into the unadmitted B11 numerical chain."""
from dataclasses import replace
from unittest import TestCase, skipUnless

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.source_atoms.backbone import start_source_backbone_numerical
from bilqis_mlx.runtime.backbone_source_bridge import admit_compiled_backbone_producer
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE
from . import test_encoding as fixtures


@skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class SourceBackboneTests(TestCase):
    setUp = fixtures.SourceEncodingTests.setUp

    def start(self, parameters=None, compiled=None, sources=None):
        return start_source_backbone_numerical(
            self.compiled if compiled is None else compiled,
            self.parameters if parameters is None else parameters,
            (self.source,) if sources is None else sources, self.schema)

    def test_real_source_runs_all_three_groups_against_literal_feedforward_equations(self):
        parameters = dict(self.parameters)
        for layer in range(12):
            prefix = f"blocks.{layer}."
            parameters[prefix + "ffn_norm"] = mx.ones((768,))
            parameters[prefix + "ffn_in"] = parameters[prefix + "ffn_in"].at[0, 0].add(.1)
            parameters[prefix + "ffn_out"] = parameters[prefix + "ffn_out"].at[0, 0].add(.2)
        session = self.start(parameters)
        self.assertEqual(session.results, ())
        expected = np.zeros((1, 2, 768), dtype=np.float32)
        expected[..., :3] = [.2, .6, .05]
        expected /= np.sqrt(np.mean(expected * expected, axis=-1, keepdims=True) + 1e-5)
        prior = None
        for group in range(1, 4):
            for _ in range(4):
                normal = expected / np.sqrt(np.mean(expected * expected, axis=-1, keepdims=True) + 1e-5)
                expected[..., 0] += .2 * np.maximum(.1 * normal[..., 0], 0) ** 2
            result = session.advance()
            np.testing.assert_allclose(np.asarray(result.hidden), expected, rtol=2e-6, atol=2e-6)
            self.assertEqual((result.group_index, result.layer_start, result.layer_end),
                             (group, 4 * (group - 1), 4 * group))
            self.assertEqual(result.admission_status, "UNADMITTED_NUMERICAL")
            if prior is not None:
                self.assertEqual(result.predecessor_digest, prior.execution_digest)
            prior = result
        with self.assertRaises(BilqisError):
            session.advance()
        with self.assertRaises(BilqisError):
            admit_compiled_backbone_producer(prior)

    def test_gradients_reach_source_identity_and_executed_backbone(self):
        parameters = dict(self.parameters)
        parameters["blocks.0.ffn_norm"] = mx.ones((768,))
        parameters["blocks.0.ffn_in"] = parameters["blocks.0.ffn_in"].at[0, 0].add(.1)
        parameters["blocks.0.ffn_out"] = parameters["blocks.0.ffn_out"].at[0, 0].add(.2)
        gradients = mx.grad(lambda values: self.start(values).advance().hidden[..., 2].sum())(parameters)
        indices = mx.array(self.source.source_row["tokens"][:2])
        selected = gradients["identity.bank.0"][indices, 2]
        self.assertTrue(bool(mx.all(mx.isfinite(selected))))
        self.assertTrue(bool(mx.all(mx.abs(selected) > 0)))
        self.assertGreater(float(mx.abs(gradients["blocks.0.ffn_out"][2, 0])), 0)

    def test_revocation_source_drift_and_missing_parameters_reject_before_execution(self):
        grant = replace(self.config.frontier.grants[0], revoked=True)
        config = replace(self.config, frontier=replace(
            self.config.frontier, grants=(grant, *self.config.frontier.grants[1:])))
        with self.assertRaises(BilqisError):
            self.start(compiled=replace(self.compiled, compiler_configs=(config,)))
        row = {**self.source.source_row, "tokens": [999, *self.source.source_row["tokens"][1:]]}
        with self.assertRaises(BilqisError):
            self.start(sources=(replace(self.source, source_row=row),))
        parameters = {name: value for name, value in self.parameters.items()
                      if name != "blocks.11.ffn_in"}
        with self.assertRaises(BilqisError):
            self.start(parameters)

    def test_caller_hidden_states_and_generation_labels_are_not_inputs(self):
        for injected in ({"hidden": mx.zeros((1, 2, 768))},
                         {"generation": "caller-generation"},
                         {"prefix_digest": "a" * 64}):
            with self.subTest(injected=tuple(injected)), self.assertRaises(TypeError):
                start_source_backbone_numerical(
                    self.compiled, self.parameters, (self.source,), self.schema, **injected)
