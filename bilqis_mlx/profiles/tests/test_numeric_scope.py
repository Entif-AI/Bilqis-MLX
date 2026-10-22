"""Numeric scope filtering must honor the source codec's list input contract."""
import unittest
from unittest.mock import patch

from bilqis_mlx.profiles.catalog import numeric_row_in_scope, partition_numeric_scope
from bilqis_mlx.semantics.numeric import calculate, number
from bilqis_mlx.source_adapters.numeric import decode, encode


class NumericScopeTests(unittest.TestCase):
    def test_in_scope_number_decodes_from_the_source_list(self):
        row = {"record": {"symbols": encode(number(3))}}
        self.assertTrue(numeric_row_in_scope(row, 3))
        self.assertFalse(numeric_row_in_scope(row, 2))

    def test_partition_checks_each_immutable_row_once(self):
        rows = ({"id": "inside"}, {"id": "outside"})
        with patch(
                "bilqis_mlx.profiles.catalog.numeric_row_in_scope",
                side_effect=(True, False)) as in_scope:
            active, deferred = partition_numeric_scope(rows, 3)
        self.assertEqual(active, [rows[0]])
        self.assertEqual(deferred, [rows[1]])
        self.assertEqual(in_scope.call_count, len(rows))

    def test_scope_requirement_reuses_identical_semantic_symbols(self):
        row = {"record": {"symbols": encode(calculate("ADD", number(2), number(3)))}}
        with patch("bilqis_mlx.profiles.catalog.decode", wraps=decode) as decoder:
            self.assertFalse(numeric_row_in_scope(row, 4))
            self.assertTrue(numeric_row_in_scope(row, 5))
            self.assertTrue(numeric_row_in_scope(row, 6))
        self.assertEqual(decoder.call_count, 1)


if __name__ == "__main__":
    unittest.main()
