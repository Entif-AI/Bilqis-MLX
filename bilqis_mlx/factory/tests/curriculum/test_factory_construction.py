"""Bounded formal fixtures exercise factory behavior without a grade trainer."""
from dataclasses import replace
import unittest

from bilqis_mlx.curriculum_compiler import (
    CapabilityNode, CurriculumAST, FiniteTypedInput, TypedExpressionTemplate,
    compile_typed_candidate_package, invalidated_typed_packages,
)
from bilqis_mlx.semantics.core import Operation, Signature
from bilqis_mlx.verification.curriculum import candidate_package_problems


class SourceTable:
    identity = "fixture:independent-truth-table/v1"

    def invoke(self, operation, values, world_contract):
        tables = {"fixture.flip": {(False,): True, (True,): False},
                  "fixture.both": {(False, False): False, (False, True): False,
                                   (True, False): False, (True, True): True}}
        return tables[operation.symbol][values]


class IndependentRules:
    identity = "fixture:separate-boolean-rules/v1"

    def invoke(self, operation, values, world_contract):
        if operation.symbol == "fixture.flip":
            return not values[0]
        if operation.symbol == "fixture.both":
            return all(values)
        raise ValueError("UNSUPPORTED_FIXTURE_OPERATION")


class FactoryConstructionTests(unittest.TestCase):
    def setUp(self):
        self.flip = Operation(900, "fixture.flip", Signature(("Boolean",), "Boolean"), "a" * 64)
        self.both = Operation(901, "fixture.both", Signature(("Boolean", "Boolean"), "Boolean"), "b" * 64)
        self.operations = {op.symbol: op for op in (self.flip, self.both)}
        self.primitive = CapabilityNode("X.ATOM", "D", (self.flip.symbol,), (), (),
                                        ("binary",), "fixture:oracle", "fixture:positive-definition", 0)
        self.dependent = replace(self.primitive, id="X.COMPOSE", roots=(self.both.symbol,),
                                 requires=(self.primitive.id,), stage=1)
        self.ast = CurriculumAST("fixture:source-only/v1", (self.primitive, self.dependent))
        bit = FiniteTypedInput("Boolean", (False, True))
        atomic = TypedExpressionTemplate(self.flip, (bit,))
        self.templates = {self.primitive.id: atomic,
                          self.dependent.id: TypedExpressionTemplate(self.both, (atomic, bit))}

    def compile(self, **changes):
        args = dict(operations=self.operations, templates=self.templates,
                    source=SourceTable(), independent=IndependentRules(),
                    qualified_prerequisites=(self.primitive.id,), seed=17, specimens_per_split=4)
        ast = changes.pop("ast", self.ast)
        args.update(changes)
        return compile_typed_candidate_package(ast, **args)

    def test_finite_construction_covers_every_operand_pattern_in_each_split(self):
        package = self.compile()
        for rows in (package.lessons, package.tests):
            composed = [row for row in rows if row.capability == self.dependent.id]
            self.assertEqual({(row.expression.arguments[0].arguments[0].value,
                               row.expression.arguments[1].value, row.proof.result)
                              for row in composed},
                             {(False, False, False), (False, True, True),
                              (True, False, False), (True, True, False)})
        self.assertEqual(package.coverage_debt, ())
        self.assertFalse(package.training_authorized)

    def test_sampling_budget_reports_uncovered_constructions(self):
        package = self.compile(specimens_per_split=1)
        self.assertIn("INCOMPLETE_FINITE_COVERAGE:X.COMPOSE:lesson:1/4", package.coverage_debt)
        self.assertIn("INCOMPLETE_FINITE_COVERAGE:X.COMPOSE:test:1/4", package.coverage_debt)

    def test_declaring_a_boolean_subdomain_cannot_erase_type_coverage_debt(self):
        primitive_only = replace(self.ast, nodes=(self.primitive,))
        template = TypedExpressionTemplate(self.flip, (FiniteTypedInput("Boolean", (False,)),))
        package = self.compile(ast=primitive_only, qualified_prerequisites=(),
                               templates={self.primitive.id: template})
        self.assertIn("INCOMPLETE_BOOLEAN_DOMAIN:X.ATOM", package.coverage_debt)

    def test_explicit_composition_edges_require_constituent_witnesses(self):
        missing = replace(self.dependent, composed_of=(self.primitive.id,))
        bit = FiniteTypedInput("Boolean", (False, True))
        templates = {**self.templates, missing.id: TypedExpressionTemplate(self.both, (bit, bit))}
        with self.assertRaisesRegex(ValueError, "MISSING_COMPOSED_CONSTITUENT:X.COMPOSE:X.ATOM"):
            self.compile(ast=replace(self.ast, nodes=(self.primitive, missing)), templates=templates)

    def test_an_undeclared_outer_operation_cannot_hide_behind_a_known_inner_root(self):
        disguised = replace(self.dependent, roots=(self.flip.symbol,))
        ast = replace(self.ast, nodes=(self.primitive, disguised))
        with self.assertRaisesRegex(ValueError, "UNDECLARED_ROOT_OPERATOR:X.COMPOSE:fixture.both"):
            self.compile(ast=ast)
        package = self.compile()
        relabeled = replace(package, ast_nodes=ast.nodes, ast_sha256=ast.digest())
        self.assertIn("GRADE_ADMISSION_CANDIDATE_PROOF_INVALID", candidate_package_problems(
            relabeled, source=SourceTable(), independent=IndependentRules()))

    def test_composed_constituent_requires_a_declared_qualified_predecessor(self):
        disguised = replace(self.dependent, roots=(self.both.symbol, self.flip.symbol), requires=())
        with self.assertRaisesRegex(ValueError, "UNQUALIFIED_CONSTITUENT:X.COMPOSE:fixture.flip"):
            self.compile(ast=replace(self.ast, nodes=(self.primitive, disguised)))

    def test_generation_orders_prior_stages_before_their_dependents(self):
        package = self.compile(ast=replace(self.ast, nodes=(self.dependent, self.primitive)))
        self.assertEqual(tuple(row.capability for row in package.lessons),
                         (self.primitive.id,) * 4 + (self.dependent.id,) * 4)

    def test_finite_proof_budget_fails_before_unbounded_expansion(self):
        with self.assertRaisesRegex(ValueError, "FINITE_CONSTRUCTION_BUDGET"):
            self.compile(construction_budget=3)

    def test_semantic_edit_invalidates_dependents_and_preserves_old_receipts(self):
        package = self.compile()
        original = tuple(row.proof for row in package.tests)
        revised = replace(self.flip, contract_sha256="c" * 64)
        self.assertEqual(invalidated_typed_packages(
            package, self.ast, {self.flip.symbol: revised, self.both.symbol: self.both}),
            ("X.ATOM", "X.COMPOSE"))
        self.assertEqual(tuple(row.proof for row in package.tests), original)
        self.assertEqual(package.operation_bindings[0].contract_sha256, "b" * 64)


if __name__ == "__main__":
    unittest.main()
