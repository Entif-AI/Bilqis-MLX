"""Real A05/A01 source ingress into the unadmitted B11 numerical chain."""
from dataclasses import replace
from unittest import TestCase, skipUnless

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.source_atoms.backbone import (
    ProducedBackboneBoundary, start_source_backbone_numerical,
    start_source_backbone_producer,
)
from bilqis_mlx.runtime.backbone_source_bridge import admit_compiled_backbone_producer
from bilqis_mlx.runtime.block_attnres import (
    DepthFrameFeatures, depth_parameter_view, depth_select,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
)
from bilqis_mlx.runtime.tests.depth.depth_helpers import _released_features
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

    def producer(self, parameters=None):
        return start_source_backbone_producer(
            self.compiled, self.parameters if parameters is None else parameters,
            (self.source,), self.schema)

    def depth_inputs(self):
        released = _released_features(1)
        features = DepthFrameFeatures(
            ((released.requests[0][0], released.requests[0][1]),),
            released.features, 1)
        extents = GenerationExtents(
            1, 1, "a" * 64, "b" * 64, features.features.digest)
        full = {item.name: mx.zeros(item.shape, dtype=mx.float32)
                for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)}
        full["depth.norm"] = mx.ones((768,), dtype=mx.float32)
        full["depth.value"] = full["depth.value"].at[0, 0].add(1)
        full["depth.output"] = full["depth.output"].at[0, 0].add(1)
        return features, depth_parameter_view(
            full, spec=ModelTopologySpecV2(), extents=extents, boundary_group=1)

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

    def test_producer_owns_h0_and_ordered_group_receipts(self):
        producer = self.producer()
        self.assertEqual(tuple(item.source_id for item in producer.receipts), ("h0",))
        receipts = [producer.receipts[0]]
        for expected in ("g1", "g2", "g3"):
            receipt = producer.advance()
            self.assertIs(type(receipt), ProducedBackboneBoundary)
            self.assertEqual(receipt.source_id, expected)
            self.assertEqual(receipt.predecessor_receipt_digest,
                             receipts[-1].receipt_digest)
            receipts.append(receipt)
        self.assertEqual(tuple(item.completed_layer for item in receipts), (0, 4, 8, 12))
        self.assertEqual(receipts[1].motif_disposition, "NO_HIT_QUARANTINED")
        self.assertEqual(receipts[1].motif_read_position,
                         "AFTER_LAYER_4_BEFORE_CAPTURE")
        self.assertEqual(tuple(item.motif_disposition for item in receipts[2:]),
                         ("NOT_APPLICABLE", "NOT_APPLICABLE"))

    def test_g2_cannot_be_relabelled_as_g1_or_mixed_into_public_selector(self):
        producer = self.producer()
        first, second = producer.advance(), producer.advance()
        with self.assertRaises(ValueError):
            replace(second, source_id="g1", completed_layer=4)
        features, view = self.depth_inputs()
        with self.assertRaises(BilqisError):
            depth_select(first.hidden, (producer.receipts[0], second), features, view)

    def test_same_extents_different_parameter_tree_cannot_reuse_receipts(self):
        first = self.producer()
        changed = dict(self.parameters)
        changed["blocks.0.ffn_in"] = changed["blocks.0.ffn_in"].at[0, 0].add(.25)
        second = self.producer(changed)
        first_g1, second_g1 = first.advance(), second.advance()
        self.assertNotEqual(first_g1.parameter_tree_digest,
                            second_g1.parameter_tree_digest)
        self.assertNotEqual(first_g1.receipt_digest, second_g1.receipt_digest)
        features, view = self.depth_inputs()
        with self.assertRaises(BilqisError):
            depth_select(first_g1.hidden, (first.receipts[0], second_g1), features, view)

    def test_public_b05_selection_keeps_gradient_to_executed_backbone(self):
        features, view = self.depth_inputs()
        parameters = dict(self.parameters)
        parameters["blocks.0.ffn_norm"] = mx.ones((768,), dtype=mx.float32)
        parameters["blocks.0.ffn_in"] = parameters["blocks.0.ffn_in"].at[0, 0].add(.1)
        parameters["blocks.0.ffn_out"] = parameters["blocks.0.ffn_out"].at[2, 0].add(.2)

        def objective(parameters):
            producer = self.producer(parameters)
            group = producer.advance()
            selected = depth_select(group.hidden, producer.receipts, features, view)
            return mx.sum(selected[..., 2])

        gradients = mx.grad(objective)(parameters)
        self.assertGreater(float(mx.abs(gradients["blocks.0.ffn_out"]).sum()), 0)
        indices = mx.array(self.source.source_row["tokens"][:2])
        self.assertTrue(bool(mx.all(mx.abs(
            gradients["identity.bank.0"][indices, 2]) > 0)))
