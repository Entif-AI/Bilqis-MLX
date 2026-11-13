"""Concrete number-set meaning and partial arithmetic, independently verified."""
import unittest

from bilqis_mlx.semantics.foundation.numeric import number, number_set, calculate, evaluate
from bilqis_mlx.source_adapters.numeric import encode, decode
from bilqis_mlx.verification.numeric import independent_value


class NumericSemanticsTests(unittest.TestCase):
    def test_count_is_set_cardinality_invariant_under_permutation(self):
        for n in range(11):
            a = calculate("COUNT", number_set(tuple(range(n))))
            b = calculate("COUNT", number_set(tuple(reversed(range(n)))))
            self.assertEqual(evaluate(a), n)
            self.assertEqual(evaluate(a), independent_value(a))
            self.assertEqual(evaluate(a), evaluate(b))

    def test_successor_and_exact_division_include_zero_and_reject_undefined_forms(self):
        self.assertEqual(evaluate(calculate("SUCC", number(3))), 4)
        self.assertEqual(evaluate(calculate("DIV", number(12), number(3))), 4)
        self.assertEqual(independent_value(calculate("DIV", number(0), number(3))), 0)
        for a, b in ((0, 0), (3, 0), (3, 2)):
            with self.subTest(a=a, b=b), self.assertRaisesRegex(ValueError, "EXACT_DIVISION"):
                evaluate(calculate("DIV", number(a), number(b)))
            with self.subTest(independent=(a,b)), self.assertRaisesRegex(ValueError,"EXACT_DIVISION"):
                independent_value(calculate("DIV", number(a), number(b)))
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            number_set((1, 1))

    def test_typed_composition_and_codec_roundtrip(self):
        value = calculate("ADD", calculate("COUNT", number_set((0, 1))),
                          calculate("COUNT", number_set((2, 3, 4))))
        self.assertEqual(evaluate(value), 5)
        self.assertEqual(independent_value(value), 5)
        self.assertEqual(decode(encode(value)), value)
        with self.assertRaises(ValueError):
            calculate("ADD", number_set((1,)), number(2))
        for bad in (encode(value)[:-1], encode(value) + ["syntax.end"], ["unknown"]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                decode(bad)
