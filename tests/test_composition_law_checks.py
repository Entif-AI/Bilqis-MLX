"""Behavioral finite-law verification, including actual countermodels."""
import unittest

from bilqis_mlx.composition.core import Operation, Signature, TypedError, curry, literal
from bilqis_mlx.composition.law_checks import LawContract, check_finite_equivalence


class BooleanBackend:
    def __init__(self, identity):
        self.identity = identity

    def invoke(self, operation, values, world_contract):
        if operation.symbol == "negate":
            return not values[0]
        if operation.symbol == "conjoin":
            return values[0] and values[1]
        raise AssertionError("unsupported fixture operator")


class LawCheckTests(unittest.TestCase):
    def setUp(self):
        self.negate = Operation(0, "negate", Signature(("Boolean",), "Boolean"), "a" * 64)
        self.source = BooleanBackend("source-fixture")
        self.independent = BooleanBackend("independent-fixture")

    def test_exhaustive_double_negation_equivalence_has_finite_scope(self):
        inputs = [curry(self.negate)(literal(bit, "Boolean")) for bit in (False, True)]
        contract = LawContract("registered-law", "release-1", "source-claim-1",
                               "Boolean", None, lambda _: True,
                               lambda expression: curry(self.negate)(curry(self.negate)(expression)))
        result = check_finite_equivalence(contract, inputs, source=self.source,
                                           independent=self.independent, scope="2 Boolean inputs")
        self.assertEqual((result.status, result.evaluated, result.scope),
                         ("VERIFIED_FINITE_SCOPE", 2, "2 Boolean inputs"))

    def test_false_equivalence_returns_actual_countermodel(self):
        expressions = [curry(self.negate)(literal(bit, "Boolean")) for bit in (False, True)]
        contract = LawContract("registered-false-law", "release-1", "source-claim-2",
                               "Boolean", None, lambda _: True,
                               lambda expression: curry(self.negate)(expression))
        result = check_finite_equivalence(contract, expressions, source=self.source,
                                           independent=self.independent, scope="Boolean domain")
        self.assertEqual((result.status, result.evaluated, result.original_result,
                          result.transformed_result), ("COUNTEREXAMPLE", 1, True, False))
        self.assertNotEqual(result.original_sha256, result.transformed_sha256)

    def test_vacuous_law_is_unknown_not_success(self):
        expression = curry(self.negate)(literal(False, "Boolean"))
        contract = LawContract("registered-law", "release-1", "source-claim-1",
                               "Boolean", None, lambda _: False, lambda x: x)
        result = check_finite_equivalence(contract, (expression,), source=self.source,
                                           independent=self.independent, scope="one candidate")
        self.assertEqual((result.status, result.evaluated),
                         ("UNKNOWN_NO_APPLICABLE_CASES", 0))

    def test_transformed_world_or_type_drift_fails(self):
        expression = curry(self.negate)(literal(False, "Boolean"))
        contract = LawContract("registered-law", "release-1", "source-claim-1",
                               "Boolean", None, lambda _: True,
                               lambda _: literal("other", "Entity"))
        with self.assertRaisesRegex(TypedError, "LAW_INVALID_TRANSFORMATION"):
            check_finite_equivalence(contract, (expression,), source=self.source,
                                     independent=self.independent, scope="one candidate")

    def test_source_and_independent_disagreement_fails_closed(self):
        expression = curry(self.negate)(literal(False, "Boolean"))
        contract = LawContract("registered-law", "release-1", "source-claim-1",
                               "Boolean", None, lambda _: True, lambda x: x)
        class WrongBackend(BooleanBackend):
            def invoke(self, operation, values, world_contract):
                return False
        with self.assertRaisesRegex(TypedError, "COMPOSITION_ORACLE_DISAGREEMENT"):
            check_finite_equivalence(contract, (expression,), source=self.source,
                                     independent=WrongBackend("wrong"), scope="one candidate")


if __name__ == "__main__":
    unittest.main()
