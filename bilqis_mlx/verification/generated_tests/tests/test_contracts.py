"""Generated-test selection uses declared types and laws."""
import unittest
from bilqis_mlx.verification.generated_tests.contracts import select_families


class FamilySelectionTests(unittest.TestCase):
    def test_integer_selection_keeps_boolean_only_family_independent(self):
        self.assertEqual(select_families('type:integer'), (
            'integer.direct', 'integer.truth', 'integer.equivalence',
            'integer.inverse_negation'))
        self.assertEqual(select_families('family:boolean.constants'), ('boolean.constants',))
        with self.assertRaisesRegex(ValueError, 'SEMANTIC_TEST_SELECTOR_UNSUPPORTED:type:imaginary'):
            select_families('type:imaginary')
