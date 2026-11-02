"""Contract cases retain literal Boolean meaning and evaluation partition."""
import unittest
from bilqis_mlx.verification.generated_tests.cases import _generated_cases
from bilqis_mlx.verification.generated_tests.contracts import Family
from bilqis_mlx.verification.generated_tests.validation import _validate_case


class BooleanCaseTests(unittest.TestCase):
    def test_boolean_cases_keep_positive_and_negative_gold(self):
        cases = _generated_cases(Family('boolean.constants', ('Boolean',), 'Boolean'),
                                 {'rows': []}, None, {})
        self.assertEqual([(c['expected'], c['partition'], c['law'], c['type']) for c in cases], [
            (False, 'development', 'boolean_constant', 'Boolean'),
            (True, 'development', 'boolean_constant', 'Boolean')])
        for case in cases:
            _validate_case(case, None, {}, None, 'boolean.constants')
        with self.assertRaisesRegex(ValueError, 'SEMANTIC_TEST_INTEGRITY_BOOLEAN_GOLD'):
            _validate_case({**cases[0], 'expected': 'untyped'}, None, {}, None, 'boolean.constants')
