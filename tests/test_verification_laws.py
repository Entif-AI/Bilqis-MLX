"""Behavioral finite-law verification, including actual countermodels."""
from pathlib import Path
import unittest

from bilqis_mlx.semantics.catalog import Catalog
from bilqis_mlx.semantics.core import Operation, Signature, TypedError, literal
from bilqis_mlx.semantics.functions import curry
from bilqis_mlx.semantics.laws import LawCandidate, LawErrorCode, SourceLocator
from bilqis_mlx.verification.laws import LawCheck, check_finite_equivalence
from bilqis_mlx.verification.outcomes import LawCheckStatus
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.registry_ast import load_registry
from bilqis_mlx.source_adapters import bind_source_catalog
from bilqis_mlx.token_atlas import ORIGINAL_GRAPH_DIGEST
from tests.support.boolean_backends import SourceBooleanBackend, SymbolicBooleanBackend


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "vendor" / "legacy-v16"
SNAPSHOT = ROOT / "docs/CURRICULUM_REGISTRY_SNAPSHOT_20261015.json"


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
        self.catalog = Catalog((self.negate,))
        self.source = BooleanBackend("source-fixture")
        self.independent = BooleanBackend("independent-fixture")
        self.locator = SourceLocator("fixture-boolean-source", "fixture-revision-1", "negate")

    def candidate(self, transform, precondition=lambda _: True):
        return LawCandidate(self.negate, self.locator, "Boolean", None,
                            precondition, transform)

    def test_exhaustive_double_negation_equivalence_has_finite_scope(self):
        inputs = [curry(self.negate)(literal(bit, "Boolean")) for bit in (False, True)]
        contract = self.candidate(
            lambda expression: curry(self.negate)(curry(self.negate)(expression)))
        result = check_finite_equivalence(contract, inputs, catalog=self.catalog, source=self.source,
                                           independent=self.independent, scope="2 Boolean inputs")
        self.assertEqual((result.status, result.evaluated, result.scope),
                         (LawCheckStatus.VERIFIED_FINITE_SCOPE, 2, "2 Boolean inputs"))
        self.assertEqual(result.subject_token_index, self.negate.token_index)
        self.assertEqual(result.subject_contract_sha256, self.negate.contract_sha256)

    def test_false_equivalence_returns_actual_countermodel(self):
        expressions = [curry(self.negate)(literal(bit, "Boolean")) for bit in (False, True)]
        contract = self.candidate(lambda expression: curry(self.negate)(expression))
        result = check_finite_equivalence(contract, expressions, catalog=self.catalog, source=self.source,
                                           independent=self.independent, scope="Boolean domain")
        self.assertEqual((result.status, result.evaluated, result.original_result,
                          result.transformed_result),
                         (LawCheckStatus.COUNTEREXAMPLE, 1, True, False))
        self.assertNotEqual(result.original_sha256, result.transformed_sha256)

    def test_vacuous_law_is_unknown_not_success(self):
        expression = curry(self.negate)(literal(False, "Boolean"))
        contract = self.candidate(lambda x: x, precondition=lambda _: False)
        result = check_finite_equivalence(contract, (expression,), catalog=self.catalog, source=self.source,
                                           independent=self.independent, scope="one candidate")
        self.assertEqual((result.status, result.evaluated),
                         (LawCheckStatus.UNKNOWN_NO_APPLICABLE_CASES, 0))

    def test_transformed_world_or_type_drift_fails(self):
        expression = curry(self.negate)(literal(False, "Boolean"))
        contract = self.candidate(lambda _: literal("other", "Entity"))
        with self.assertRaisesRegex(TypedError, LawErrorCode.INVALID_TRANSFORMATION.value):
            check_finite_equivalence(contract, (expression,), catalog=self.catalog, source=self.source,
                                     independent=self.independent, scope="one candidate")

    def test_source_and_independent_disagreement_fails_closed(self):
        expression = curry(self.negate)(literal(False, "Boolean"))
        contract = self.candidate(lambda x: x)
        class WrongBackend(BooleanBackend):
            def invoke(self, operation, values, world_contract):
                return False
        with self.assertRaisesRegex(TypedError, "COMPOSITION_ORACLE_DISAGREEMENT"):
            check_finite_equivalence(contract, (expression,), catalog=self.catalog, source=self.source,
                                     independent=WrongBackend("wrong"), scope="one candidate")

    def test_unproven_source_and_invalid_candidate_fail_at_boundary(self):
        with self.assertRaisesRegex(TypedError, LawErrorCode.MISSING_SOURCE_LOCATOR.value):
            SourceLocator("fixture-boolean-source", "", "negate")
        with self.assertRaisesRegex(TypedError, LawErrorCode.INVALID_CANDIDATE.value):
            LawCandidate(self.negate, self.locator, "Entity", None,
                         lambda _: True, lambda x: x)

    def test_candidate_and_result_must_bind_current_catalog_contracts(self):
        expression = curry(self.negate)(literal(False, "Boolean"))
        tampered = Operation(0, "negate", self.negate.signature, "b" * 64)
        forged = LawCandidate(tampered, self.locator, "Boolean", None,
                              lambda _: True, lambda x: x)
        with self.assertRaisesRegex(TypedError, LawErrorCode.SUBJECT_NOT_CATALOG_BOUND.value):
            check_finite_equivalence(forged, (expression,), catalog=self.catalog,
                                     source=self.source, independent=self.independent,
                                     scope="one candidate")
        extra = Operation(1, "negate", self.negate.signature, "c" * 64)
        wrong_output = self.candidate(lambda expr: curry(extra)(expr))
        with self.assertRaisesRegex(TypedError, "COMPOSITION_UNKNOWN_CATALOG_ID"):
            check_finite_equivalence(wrong_output, (expression,), catalog=self.catalog,
                                     source=self.source, independent=self.independent,
                                     scope="one candidate")

    def test_a_receipt_cannot_claim_success_without_evaluated_evidence(self):
        with self.assertRaisesRegex(TypedError, LawErrorCode.INVALID_CHECK_RECEIPT.value):
            LawCheck(self.negate.token_index, self.negate.contract_sha256,
                     self.locator, LawCheckStatus.VERIFIED_FINITE_SCOPE,
                     "empty candidate pool", 0)
        with self.assertRaisesRegex(TypedError, LawErrorCode.INVALID_CHECK_RECEIPT.value):
            LawCheck(self.negate.token_index, self.negate.contract_sha256,
                     self.locator, LawCheckStatus.COUNTEREXAMPLE,
                     "one candidate", 1)


class OriginalSourceLawTests(unittest.TestCase):
    """An original token from the code-bound registry, not an invented rule ID."""

    @classmethod
    def setUpClass(cls):
        tokens = load_registry(SNAPSHOT).tokens
        micro, _, graph, _, _ = read_sources(SOURCE_ROOT)
        cls.catalog = bind_source_catalog(tokens, graph, ("cogal.operator.NOT",),
                                          historical_graph_sha256=ORIGINAL_GRAPH_DIGEST)
        cls.negate = cls.catalog.resolve_external_name("cogal.operator.NOT")
        names = {cls.negate.token_index: "NOT"}
        cls.source = SourceBooleanBackend(micro.boolean, names)
        cls.independent = SymbolicBooleanBackend(names)
        cls.locator = SourceLocator(
            "bilqis-triplets-v16/bilqis_logic/kernel.py",
            ORIGINAL_GRAPH_DIGEST,
            "cogal.operator.NOT",
        )

    def test_original_not_double_negation_matches_source_and_sympy(self):
        expressions = tuple(curry(self.negate)(literal(x, "Boolean"))
                            for x in (False, True))
        candidate = LawCandidate(
            self.negate, self.locator, "Boolean", None,
            lambda _: True,
            lambda expr: curry(self.negate)(curry(self.negate)(expr)),
        )
        receipt = check_finite_equivalence(
            candidate, expressions, catalog=self.catalog, source=self.source,
            independent=self.independent, scope="complete Boolean input domain",
        )
        self.assertEqual(receipt.status, LawCheckStatus.VERIFIED_FINITE_SCOPE)
        self.assertEqual(receipt.evaluated, 2)
        self.assertEqual(receipt.subject_token_index, self.negate.token_index)
        self.assertEqual(receipt.source, self.locator)


if __name__ == "__main__":
    unittest.main()
