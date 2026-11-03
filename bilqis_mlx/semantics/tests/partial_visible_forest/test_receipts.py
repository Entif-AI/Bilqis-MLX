"""Stable public identities for source-owned partial-forest receipts."""
import pickle
from unittest import TestCase

from bilqis_mlx.semantics import partial_visible_forest
from bilqis_mlx.semantics.frame_compiler import compile_prefix
from bilqis_mlx.semantics.tests.frame_compiler.fixtures import RELEASE, _mixed_case


class PartialReceiptTests(TestCase):
    def test_receipt_and_hidden_provenance_keep_canonical_pickle_identity(self):
        ast, config = _mixed_case()
        receipt = partial_visible_forest.validate_partial_visible_forest(
            compile_prefix(ast, 4, RELEASE, config), ast, config)
        self.assertEqual(len(receipt.hidden_parents), 1)
        for value in (receipt, receipt.hidden_parents[0]):
            with self.subTest(record=type(value).__name__):
                self.assertEqual(
                    type(value).__module__, partial_visible_forest.__name__)
                restored = pickle.loads(pickle.dumps(value))
                self.assertIs(type(restored), type(value))
                self.assertEqual(restored, value)
        self.assertEqual(
            partial_visible_forest.validate_partial_visible_forest(
                compile_prefix(ast, 4, RELEASE, config), ast, config,
                expected_receipt=receipt), receipt)
