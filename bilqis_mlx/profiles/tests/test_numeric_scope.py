"""Numeric scope filtering must honor the source codec's list input contract."""
import unittest

from bilqis_mlx.profiles.catalog import numeric_row_in_scope
from bilqis_mlx.semantics.numeric import number
from bilqis_mlx.source_adapters.numeric import encode


class NumericScopeTests(unittest.TestCase):
    def test_in_scope_number_decodes_from_the_source_list(self):
        row = {"record": {"symbols": encode(number(3))}}
        self.assertTrue(numeric_row_in_scope(row, 3))
        self.assertFalse(numeric_row_in_scope(row, 2))


if __name__ == "__main__":
    unittest.main()
