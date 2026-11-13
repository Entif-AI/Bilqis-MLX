"""Contract tests for pure, grade-independent typed functional composition."""
from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
from itertools import product
from pathlib import Path
import unittest

from bilqis_mlx.semantics import (
    Catalog, Curried, Operation, Signature, TypedError, compose, curry,
    expression_digest, lift2, literal, partial_apply,
)
from bilqis_mlx.source_adapters import bind_source_catalog
from bilqis_mlx.verification import (
    ProofStatus, exhaustive_boolean_cases, verify, verify_constituents,
)
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_b_oracle import CONNECTIVES
from bilqis_mlx.live_grade_b import independent_truth
from bilqis_mlx.registry_ast import load_registry
from bilqis_mlx.token_atlas import ORIGINAL_GRAPH_DIGEST
from tests.support.boolean_backends import (
    FaultyBooleanBackend, SourceBooleanBackend, SymbolicBooleanBackend,
)


ROOT = Path(__file__).resolve().parents[4]
SOURCE_ROOT = ROOT / "vendor" / "legacy-v16"
SNAPSHOT = ROOT / "docs/provenance/CURRICULUM_REGISTRY_SNAPSHOT_20261015.json"


class SemanticAlgebraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokens = load_registry(SNAPSHOT).tokens
        micro, _, graph, _, _ = read_sources(SOURCE_ROOT)
        cls.graph = graph
        source_names = {"cogal.operator." + name: name for name in CONNECTIVES}
        cls.catalog = bind_source_catalog(cls.tokens, graph, source_names,
                                          historical_graph_sha256=ORIGINAL_GRAPH_DIGEST)
        operations = tuple(cls.catalog.resolve_external_name(name)
                           for name in source_names)
        cls.names = {op.token_index: source_names[op.symbol] for op in operations}
        for op in operations:
            if cls.graph["tokens"][op.token_index] != op.symbol:
                raise AssertionError("Historical source token identity drift")
        cls.source = SourceBooleanBackend(micro.boolean, cls.names)
        cls.symbolic = SymbolicBooleanBackend(cls.names)

    def operation(self, name):
        return next(self.catalog.get(token_id)
                    for token_id, alias in self.names.items() if alias == name)

    def test_all_six_original_operators_and_twenty_two_boolean_cases(self):
        checked = 0
        for token_id, name in self.names.items():
            operation = self.catalog.get(token_id)
            arity = 1 if name == "NOT" else 2
            self.assertEqual(len(operation.signature.inputs), arity)
            for bits in product((False, True), repeat=arity):
                expr = curry(operation)(*(literal(value, "Boolean") for value in bits))
                proof = verify(expr, source=self.source, independent=self.symbolic)
                self.assertEqual(proof.status, ProofStatus.VERIFIED)
                self.assertEqual(proof.result, independent_truth(name, bits))
                self.assertEqual(len(proof.expression_sha256), 64)
                checked += 1
        self.assertEqual(checked, 22)

    def test_lift_currying_and_composition_preserve_inspectable_ast(self):
        left = literal(True, "Boolean")
        right = literal(False, "Boolean")
        xor = self.operation("XOR")
        composed = lift2(xor)(left)(right)
        direct = curry(xor)(left, right)
        self.assertEqual(expression_digest(composed), expression_digest(direct))
        self.assertTrue(verify(composed, source=self.source,
                               independent=self.symbolic).result)
        inside_not = compose(self.operation("NOT"), self.operation("AND"))(
            left, right)
        self.assertTrue(verify(inside_not, source=self.source,
                               independent=self.symbolic).result)
        self.assertIsInstance(curry(self.operation("AND"))(left), Curried)

    def test_partial_application_binds_arbitrary_argument_positions(self):
        operation = self.operation("IMPLIES")
        builder = partial_apply(operation, bound={1: literal(False, "Boolean")})
        expr = builder(literal(True, "Boolean"))
        self.assertFalse(verify(expr, source=self.source,
                                independent=self.symbolic).result)
        with self.assertRaisesRegex(TypedError, "TOO_MANY_ARGUMENTS"):
            curry(operation)(literal(True, "Boolean"), literal(False, "Boolean"),
                             literal(True, "Boolean"))
        with self.assertRaisesRegex(TypedError, "PARTIAL_SLOT_OUT_OF_RANGE"):
            partial_apply(operation, bound={2: literal(True, "Boolean")})
        with self.assertRaisesRegex(TypedError, "INVALID_CURRIED_BINDINGS"):
            Curried(operation, ((1, literal(True, "Boolean")),
                                (1, literal(False, "Boolean"))))

    def test_type_arity_and_cross_world_mismatch_are_rejected(self):
        with self.assertRaisesRegex(TypedError, "ARGUMENT_TYPE_MISMATCH"):
            curry(self.operation("NOT"))(literal("A", "Entity"))
        with self.assertRaisesRegex(TypedError, "INCOMPATIBLE_WORLD_CONTRACT"):
            lift2(self.operation("AND"))(
                literal(True, "Boolean", world_contract="micro"))(
                literal(False, "Boolean", world_contract="development"))
        with self.assertRaisesRegex(TypedError, "BOOLEAN_LITERAL_TYPE_DRIFT"):
            literal("TRUE", "Boolean")
        with self.assertRaisesRegex(TypedError, "UNIFICATION_FAILED"):
            compose(self.operation("XOR"), self.operation("AND"))
        with self.assertRaisesRegex(TypedError, "LIFT_REQUIRES_BINARY_OPERATOR"):
            lift2(self.operation("NOT"))

    def test_external_name_change_is_not_a_semantic_change(self):
        op = self.operation("XOR")
        a = literal(True, "Boolean")
        b = literal(False, "Boolean")
        old = curry(op)(a, b)
        renamed = replace(op, symbol="different display name")
        self.assertEqual(expression_digest(old), expression_digest(
            curry(renamed)(a, b)))
        revised = replace(op, contract_sha256="a" * 64)
        self.assertNotEqual(expression_digest(old), expression_digest(
            curry(revised)(a, b)))
        with self.assertRaisesRegex(TypedError, "DUPLICATE_CATALOG_BINDING"):
            Catalog((op, renamed))
        with self.assertRaisesRegex(TypedError, "UNKNOWN_CATALOG_ID"):
            self.catalog.get(999999)
        with self.assertRaisesRegex(TypedError, "INVALID_CATALOG_ID"):
            self.catalog.get(True)

    def test_oracle_disagreement_and_shared_oracle_identity_fail(self):
        expr = curry(self.operation("XOR"))(literal(True, "Boolean"),
                                             literal(False, "Boolean"))
        with self.assertRaisesRegex(TypedError, "ORACLE_DISAGREEMENT"):
            verify(expr, source=self.source,
                   independent=FaultyBooleanBackend(self.names))
        with self.assertRaisesRegex(TypedError, "INDEPENDENT_PROOF_REQUIRED"):
            verify(expr, source=self.source, independent=self.source)

    def test_original_entity_signature_partially_applies_without_new_code(self):
        eq = next(token for token in self.tokens
                  if token.symbol == "micro.compare.EQ")
        op = Operation(eq.id, eq.symbol, Signature.parse(eq.signature),
                       eq.contract_sha256, world_contract="micro")
        expr = partial_apply(
            op, bound={0: literal("A", "Entity", world_contract="micro")})(
                literal("B", "Entity", world_contract="micro"))
        self.assertEqual(expr.type_name, "Boolean")
        self.assertEqual(expr.world_contract, "micro")
        self.assertEqual(expr.operator.token_index, eq.id)
        self.assertEqual(len(expr.arguments), 2)

    def test_catalog_binding_checks_source_meaning_not_just_symbol(self):
        chosen = next(token for token in self.tokens
                      if token.symbol == "micro.compare.EQ")
        valid = bind_source_catalog(self.tokens, self.graph, (chosen.symbol,),
                                    historical_graph_sha256=ORIGINAL_GRAPH_DIGEST)
        self.assertEqual(valid.get(chosen.id).contract_sha256,
                         chosen.contract_sha256)
        changed = tuple(replace(t, contract_sha256="a" * 64)
                        if t.id == chosen.id else t for t in self.tokens)
        with self.assertRaisesRegex(TypedError, "SOURCE_MEANING_CONTRACT_DRIFT"):
            bind_source_catalog(changed, self.graph, (chosen.symbol,),
                                historical_graph_sha256=ORIGINAL_GRAPH_DIGEST)
        changed = tuple(replace(t, arity="7") if t.id == chosen.id else t
                        for t in self.tokens)
        with self.assertRaisesRegex(TypedError, "SOURCE_ARITY_DRIFT"):
            bind_source_catalog(changed, self.graph, (chosen.symbol,),
                                historical_graph_sha256=ORIGINAL_GRAPH_DIGEST)
        changed = deepcopy(self.graph)
        changed["tokens"][chosen.id] = "another.semantic"
        with self.assertRaisesRegex(TypedError, "SOURCE_TOKEN_IDENTITY_DRIFT"):
            bind_source_catalog(self.tokens, changed, (chosen.symbol,),
                                historical_graph_sha256=ORIGINAL_GRAPH_DIGEST)
        with self.assertRaisesRegex(TypedError, "UNRESOLVED_SEMANTIC_ID"):
            bind_source_catalog(self.tokens, self.graph, ("unknown.semantic",),
                                historical_graph_sha256=ORIGINAL_GRAPH_DIGEST)

    def test_full_joint_boolean_input_patterns_are_covered_and_checked(self):
        total = 0
        for name in CONNECTIVES:
            operator = self.operation(name)
            coverage = exhaustive_boolean_cases(
                operator, source=self.source, independent=self.symbolic)
            count = 2 ** len(operator.signature.inputs)
            self.assertEqual(coverage.expected_patterns, count)
            self.assertEqual(coverage.covered_patterns, count)
            self.assertEqual(len({case.arguments for case in coverage.cases}), count)
            self.assertEqual(
                [case.proof.result for case in coverage.cases],
                [independent_truth(name, bits) for bits in product(
                    (False, True), repeat=len(operator.signature.inputs))])
            total += count
        self.assertEqual(total, 22)
        with self.assertRaisesRegex(TypedError, "EXHAUSTIVE_BUDGET_EXCEEDED"):
            exhaustive_boolean_cases(self.operation("AND"), source=self.source,
                                     independent=self.symbolic, max_arity=1)
        with self.assertRaisesRegex(TypedError, "METHOD_NOT_BOOLEAN"):
            eq_token = next(t for t in self.tokens
                            if t.symbol == "micro.compare.EQ")
            op = Operation(eq_token.id, eq_token.symbol,
                           Signature.parse(eq_token.signature), eq_token.contract_sha256)
            exhaustive_boolean_cases(op, source=self.source,
                                     independent=self.symbolic)

    def test_composed_constituents_are_independently_verified(self):
        p = curry(self.operation("XOR"))(literal(True, "Boolean"),
                                          literal(False, "Boolean"))
        q = curry(self.operation("AND"))(literal(True, "Boolean"),
                                          literal(True, "Boolean"))
        result = lift2(self.operation("OR"))(p)(q)
        receipts = verify_constituents(result, source=self.source,
                                       independent=self.symbolic)
        self.assertEqual(tuple(receipt.result for receipt in receipts),
                         (True, True, True))
        self.assertEqual(len({receipt.expression_sha256 for receipt in receipts}), 3)
        self.assertEqual(receipts[-1].expression_sha256, expression_digest(result))
        with self.assertRaisesRegex(TypedError, "REQUIRES_COMPOSED_EXPRESSION"):
            verify_constituents(literal(True, "Boolean"), source=self.source,
                                 independent=self.symbolic)


if __name__ == "__main__":
    unittest.main()
