from dataclasses import replace
from bilqis_mlx.curriculum_compiler import (
    compile_ast, compile_typed_candidate_package, invalidated_typed_packages,
    FiniteTypedInput, TypedExpressionTemplate,
)
from bilqis_mlx.semantics.core import Apply, Operation, Signature

class TypedPackageCases:
    def test_generic_typed_package_compiles_unknown_primitive_and_dependent(self):
        primitive = replace(compile_ast(self.course).nodes[0],
                            id="X.PRIMITIVE", grade="A", roots=("fixture.negate",),
                            requires=(), composed_of=())
        dependent = replace(primitive, id="Y.DEPENDENT", grade="B",
                            roots=("fixture.conjoin", "fixture.negate"),
                            requires=("X.PRIMITIVE",))
        ast = replace(compile_ast(self.course), nodes=(primitive, dependent))
        negate = Operation(900, "fixture.negate", Signature(("Boolean",), "Boolean"), "a" * 64)
        conjoin = Operation(901, "fixture.conjoin", Signature(("Boolean", "Boolean"), "Boolean"), "b" * 64)

        class Backend:
            def __init__(self, identity): self.identity = identity
            def invoke(self, operation, values, world_contract):
                if operation.symbol == "fixture.negate": return not values[0]
                if operation.symbol == "fixture.conjoin": return values[0] and values[1]
                raise AssertionError(operation.symbol)

        boolean = FiniteTypedInput("Boolean", (False, True))
        negate_template = TypedExpressionTemplate(negate, (boolean,))
        templates = {
            "X.PRIMITIVE": negate_template,
            "Y.DEPENDENT": TypedExpressionTemplate(conjoin, (negate_template, boolean)),
        }

        package = compile_typed_candidate_package(
            ast, operations={"fixture.negate": negate, "fixture.conjoin": conjoin},
            templates=templates, source=Backend("source-fixture"),
            independent=Backend("independent-fixture"),
            qualified_prerequisites=("X.PRIMITIVE",), seed=17, specimens_per_split=2)
        self.assertFalse(package.training_authorized)
        self.assertEqual(package.source_status, "SOURCE_ONLY_CANDIDATE")
        self.assertEqual({row.capability for row in package.lessons},
                         {"X.PRIMITIVE", "Y.DEPENDENT"})
        self.assertEqual(len(package.lessons), 4)
        self.assertEqual(len(package.tests), 4)
        self.assertIsInstance(package.lessons[0].expression, Apply)
        self.assertEqual(len(package.lessons[0].proof.expression_sha256), 64)
        self.assertEqual(package.lessons[0].type_name, "Boolean")
        self.assertEqual(package, compile_typed_candidate_package(
            ast, operations={"fixture.negate": negate, "fixture.conjoin": conjoin},
            templates=templates, source=Backend("source-fixture"),
            independent=Backend("independent-fixture"),
            qualified_prerequisites=("X.PRIMITIVE",), seed=17, specimens_per_split=2))

        revised = Operation(900, "fixture.negate", Signature(("Boolean",), "Boolean"), "c" * 64)
        self.assertEqual(invalidated_typed_packages(
            package, ast, {"fixture.negate": revised, "fixture.conjoin": conjoin}),
            ("X.PRIMITIVE", "Y.DEPENDENT"))
        self.assertEqual(next(item for item in package.operation_bindings
                              if item.symbol == "fixture.negate").contract_sha256, "a" * 64)
        self.assertEqual(invalidated_typed_packages(
            package, replace(ast, nodes=(primitive,)),
            {"fixture.negate": negate, "fixture.conjoin": conjoin}),
            ("Y.DEPENDENT",))

    def test_generic_typed_package_reports_missing_prerequisite_and_oracle_debt(self):
        primitive = replace(compile_ast(self.course).nodes[0], id="X.PRIMITIVE",
                            grade="A", roots=("fixture.negate",), requires=(), composed_of=())
        dependent = replace(primitive, id="Y.DEPENDENT", grade="B",
                            roots=("fixture.negate",), requires=("X.PRIMITIVE",))
        ast = replace(compile_ast(self.course), nodes=(primitive, dependent))
        negate = Operation(900, "fixture.negate", Signature(("Boolean",), "Boolean"), "a" * 64)

        class Backend:
            def __init__(self, identity, invert=False): self.identity, self.invert = identity, invert
            def invoke(self, operation, values, world_contract):
                return values[0] if self.invert else not values[0]

        template = TypedExpressionTemplate(
            negate, (FiniteTypedInput("Boolean", (False, True)),))

        with self.assertRaisesRegex(ValueError,
                                    "MISSING_PREREQUISITE:Y.DEPENDENT:X.PRIMITIVE"):
            compile_typed_candidate_package(
                ast, operations={"fixture.negate": negate},
                templates={"X.PRIMITIVE": template, "Y.DEPENDENT": template},
                source=Backend("source"), independent=Backend("independent"),
                specimens_per_split=1)
        with self.assertRaisesRegex(ValueError,
                                    "ORACLE_DISAGREEMENT:X.PRIMITIVE"):
            compile_typed_candidate_package(
                replace(ast, nodes=(primitive,)), operations={"fixture.negate": negate},
                templates={"X.PRIMITIVE": template}, source=Backend("source"),
                independent=Backend("independent", invert=True), specimens_per_split=1)
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_ANSWER_TYPE:X.PRIMITIVE"):
            compile_typed_candidate_package(
                replace(ast, nodes=(replace(primitive, answers=("integer_0_3",)),)),
                operations={"fixture.negate": negate},
                templates={"X.PRIMITIVE": template}, source=Backend("source"),
                independent=Backend("independent"), specimens_per_split=1)

    def test_generic_package_rejects_invalid_graph_and_unbound_nested_operation(self):
        node = replace(compile_ast(self.course).nodes[0], id="X.COMPOSED", grade="B",
                       roots=("fixture.conjoin", "fixture.negate"),
                       requires=("X.FUTURE",), composed_of=())
        future = replace(node, id="X.FUTURE", grade="C", roots=("fixture.negate",),
                         requires=())
        invalid = replace(compile_ast(self.course), nodes=(node, future))
        negate = Operation(900, "fixture.negate", Signature(("Boolean",), "Boolean"), "a" * 64)
        conjoin = Operation(901, "fixture.conjoin", Signature(("Boolean", "Boolean"), "Boolean"), "b" * 64)
        template = TypedExpressionTemplate(conjoin, (
            TypedExpressionTemplate(negate, (FiniteTypedInput("Boolean", (True,)),)),
            FiniteTypedInput("Boolean", (False,))))

        class Backend:
            identity = "fixture"
            def invoke(self, operation, values, world_contract): return False

        with self.assertRaisesRegex(ValueError, "DEPENDENCY_NOT_EARLIER_GRADE"):
            compile_typed_candidate_package(
                invalid, operations={"fixture.negate": negate, "fixture.conjoin": conjoin},
                templates={"X.COMPOSED": template, "X.FUTURE": TypedExpressionTemplate(negate, (FiniteTypedInput("Boolean", (True,)),))},
                source=Backend(), independent=type("Independent", (Backend,), {"identity": "independent"})(),
                qualified_prerequisites=("X.FUTURE",), specimens_per_split=1)
        valid = replace(invalid, nodes=(replace(node, grade="C", stage=1),
                                        replace(future, grade="B", stage=0)))
        forged = Operation(900, "fixture.negate", Signature(("Boolean",), "Boolean"), "c" * 64)
        unbound_template = TypedExpressionTemplate(conjoin, (
            TypedExpressionTemplate(forged, (FiniteTypedInput("Boolean", (True,)),)),
            FiniteTypedInput("Boolean", (False,))))
        with self.assertRaisesRegex(ValueError, "UNBOUND_NESTED_OPERATION:X.COMPOSED:fixture.negate"):
            compile_typed_candidate_package(
                valid, operations={"fixture.negate": negate, "fixture.conjoin": conjoin},
                templates={"X.COMPOSED": unbound_template, "X.FUTURE": TypedExpressionTemplate(negate, (FiniteTypedInput("Boolean", (True,)),))},
                source=Backend(), independent=type("Independent", (Backend,), {"identity": "independent"})(),
                qualified_prerequisites=("X.FUTURE",), specimens_per_split=1)
