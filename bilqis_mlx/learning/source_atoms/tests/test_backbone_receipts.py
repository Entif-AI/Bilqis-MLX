"""Execution-owned B11 producer receipt and B05 adversaries."""
from copy import copy
from dataclasses import replace
from unittest import skipUnless

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.source_atoms.backbone_receipts import (
    ProducedBackboneBoundary, receipt_projection as _receipt_projection,
)
from bilqis_mlx.runtime.block_attnres import (
    DepthSummary, _numerical_depth_select, _rms_norm, depth_select,
)
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE
from .backbone_test_support import SourceBackboneTestBase


@skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class SourceBackboneReceiptTests(SourceBackboneTestBase):
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
        self.assertNotEqual(receipts[1].motif_read_digest, contract_digest(()))
        self.assertEqual(tuple(item.motif_disposition for item in receipts[2:]),
                         ("NOT_APPLICABLE", "NOT_APPLICABLE"))

    def test_g2_cannot_be_relabelled_as_g1_or_mixed_into_public_selector(self):
        producer = self.producer()
        first, second = producer.advance(), producer.advance()
        with self.assertRaises((TypeError, BilqisError)):
            replace(second, source_id="g1", completed_layer=4)
        features, view = self.depth_inputs(self.parameters)
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
        features, view = self.depth_inputs(self.parameters)
        with self.assertRaises(BilqisError):
            depth_select(first_g1.hidden, (first.receipts[0], second_g1), features, view)

    def test_generation_prefix_and_cache_tampering_reject_before_b05(self):
        producer = self.producer()
        group = producer.advance()
        features, view = self.depth_inputs(self.parameters)
        for field in ("generation_digest", "prefix_digest", "cache_chain_digest"):
            forged = copy(group)
            object.__setattr__(forged, field, "f" * 64)
            with self.subTest(field=field), self.assertRaises(BilqisError):
                depth_select(group.hidden, (producer.receipts[0], forged), features, view)

    def test_recomputed_receipt_forgery_and_foreign_current_reject(self):
        producer = self.producer()
        group = producer.advance()
        features, view = self.depth_inputs(self.parameters)
        forged = copy(group)
        object.__setattr__(forged, "cache_chain_digest", "f" * 64)
        object.__setattr__(forged, "receipt_digest",
                           contract_digest(_receipt_projection(forged.__dict__)))
        with self.assertRaises(BilqisError):
            depth_select(group.hidden, (producer.receipts[0], forged), features, view)
        foreign = group.hidden.at[0, 0, 0].add(.125)
        with self.assertRaises(BilqisError):
            depth_select(foreign, producer.receipts, features, view)

    def test_identity_tree_and_guarded_motif_rights_are_bound(self):
        changed = dict(self.parameters)
        changed["identity.bank.0"] = changed["identity.bank.0"].at[0, 0].add(.125)
        first, second = self.producer(), self.producer(changed)
        first_group, second_group = first.advance(), second.advance()
        self.assertNotEqual(first_group.parameter_tree_digest,
                            second_group.parameter_tree_digest)
        features, foreign_view = self.depth_inputs(changed)
        with self.assertRaises(BilqisError):
            depth_select(first_group.hidden, first.receipts, features, foreign_view)

        context = self.motif_context()
        frontier = context.frontiers[0]
        revoked = replace(frontier, grants=tuple(
            replace(grant, revoked=True) for grant in frontier.grants))
        held = replace(context, frontiers=(revoked,))
        with self.assertRaises(BilqisError):
            self.producer(motif_context=held).advance()

    def test_public_b05_matches_normalized_group_capture(self):
        parameters = dict(self.parameters)
        parameters["depth.norm"] = mx.ones((768,), dtype=mx.float32)
        producer = self.producer(parameters)
        group = producer.advance()
        features, view = self.depth_inputs(parameters)
        summaries = (
            DepthSummary("h0", 0, producer.receipts[0].hidden),
            DepthSummary("g1", 4, _rms_norm(group.hidden, view["norm"])),
        )
        expected = _numerical_depth_select(group.hidden, summaries, features, view)
        actual = depth_select(group.hidden, producer.receipts, features, view)
        np.testing.assert_allclose(np.asarray(actual), np.asarray(expected), atol=2e-6)

    def test_public_b05_selection_keeps_gradient_to_executed_backbone(self):
        parameters = dict(self.parameters)
        parameters["blocks.0.ffn_norm"] = mx.ones((768,), dtype=mx.float32)
        parameters["blocks.0.ffn_in"] = parameters["blocks.0.ffn_in"].at[0, 0].add(.1)
        parameters["blocks.0.ffn_out"] = parameters["blocks.0.ffn_out"].at[2, 0].add(.2)

        def objective(parameters):
            producer = self.producer(parameters)
            group = producer.advance()
            features, view = self.depth_inputs(parameters)
            selected = depth_select(group.hidden, producer.receipts, features, view)
            return mx.sum(selected[..., 2])

        gradients = mx.grad(objective)(parameters)
        self.assertGreater(float(mx.abs(gradients["blocks.0.ffn_out"]).sum()), 0)
        indices = mx.array(self.source.source_row["tokens"][:2])
        self.assertTrue(bool(mx.all(mx.abs(
            gradients["identity.bank.0"][indices, 2]) > 0)))
