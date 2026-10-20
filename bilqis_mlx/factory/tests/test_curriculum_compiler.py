"""Neural-inert proof that curriculum structure generates reusable probes."""
import json
from dataclasses import replace
from pathlib import Path
import unittest

from bilqis_mlx.curriculum_compiler import (compile_ast, compile_probe_plan,
                                          diagnose_coverage, materialize_probes,
                                          dependency_coverage_plan,
                                          affected_dependency_closure,
                                          compile_typed_candidate_package,
                                          invalidated_typed_packages,
                                          FiniteTypedInput, TypedExpressionTemplate)
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.semantics.core import Apply, Operation, Signature


class CurriculumCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[3]
        cls.course = accepted_grade_a(json.loads(
            (root / 'docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json').read_text()))

    def test_grade_a_compiles_into_typed_semantic_nodes(self):
        ast = compile_ast(self.course)
        self.assertEqual(len(ast.nodes), 6)
        self.assertFalse(ast.authorized_for_training)
        self.assertEqual(ast.nodes[0].id, 'A.IDENTITY')
        self.assertEqual(ast.nodes[0].roots, ('micro.compare.EQ',))
        self.assertEqual(ast.digest(), compile_ast(self.course).digest())

    def test_probe_cross_product_deterministic_and_nonadmitted(self):
        ast = compile_ast(self.course)
        plans = compile_probe_plan(ast, variants_per_axis=5)
        self.assertEqual(len(plans), 6 * 2 * 2 * 5)
        self.assertEqual(len({r['probe_id'] for r in plans}), len(plans))
        self.assertEqual(plans, compile_probe_plan(ast, variants_per_axis=5))
        self.assertEqual(diagnose_coverage(ast, plans), ())
        self.assertTrue(all('gold' not in r and 'tokens' not in r for r in plans))

    def test_narrow_variation_cannot_masquerade_as_coverage(self):
        ast = compile_ast(self.course)
        plans = compile_probe_plan(ast)
        narrowed = [r for r in plans if r['variant'] == 0]
        self.assertEqual(len(diagnose_coverage(ast, narrowed)), 6)
        with self.assertRaisesRegex(ValueError, 'TOO_NARROW'):
            compile_probe_plan(ast, variants_per_axis=1)

    def test_dependency_coverage_tracks_new_and_revised_semantics(self):
        ast = compile_ast(self.course)
        prototype = replace(ast.nodes[0], id='C.NEW', grade='C',
                            requires=('A.IDENTITY', 'A.EDGE'))
        expanded = replace(ast, nodes=(*ast.nodes, prototype))
        plan = dependency_coverage_plan(expanded,
                                         supported_edges=(('C.NEW', 'A.IDENTITY'),))
        self.assertEqual([(p['predecessor'], p['status']) for p in plan],
                         [('A.EDGE', 'MISSING_CONSTRUCTOR'),
                          ('A.IDENTITY', 'CONSTRUCTOR_DECLARED_UNVERIFIED')])
        self.assertTrue(all(p['coverage_debt'] for p in plan))
        revised = replace(expanded, nodes=(*ast.nodes, replace(
            prototype, requires=('A.MAPS',))))
        self.assertEqual(dependency_coverage_plan(revised)[0]['predecessor'],
                         'A.MAPS')
        self.assertFalse(dependency_coverage_plan(revised)[0]['training_authorized'])
        with self.assertRaisesRegex(ValueError, 'UNDECLARED_SUPPORTED_EDGE'):
            dependency_coverage_plan(revised,
                                     supported_edges=(('C.NEW', 'A.IDENTITY'),))
        with self.assertRaisesRegex(ValueError, 'UNRESOLVED_DEPENDENCY'):
            dependency_coverage_plan(replace(ast, nodes=(*ast.nodes, replace(
                prototype, requires=('A.UNKNOWN',)))))

    def test_same_grade_prerequisites_require_an_earlier_teaching_stage(self):
        staged = replace(self.course.grades[0], teaching_stages=tuple(
            (cap.id,) for cap in self.course.grades[0].capabilities))
        compiled = compile_ast(replace(self.course, grades=(staged,)))
        self.assertEqual(tuple(node.stage for node in compiled.nodes),
                         tuple(range(len(staged.capabilities))))
        count = replace(compiled.nodes[0], id='C.COUNT', grade='C', stage=0)
        number = replace(compiled.nodes[0], id='C.NUMBER', grade='C', stage=1,
                         requires=('C.COUNT',))
        add = replace(compiled.nodes[0], id='C.ADD', grade='C', stage=2,
                      requires=('C.NUMBER', 'C.COUNT'))
        candidate = replace(compiled, nodes=(*compiled.nodes, count, number, add))
        edges = dependency_coverage_plan(candidate)
        self.assertEqual({(x['capability'], x['predecessor']) for x in edges},
                         {('C.NUMBER', 'C.COUNT'), ('C.ADD', 'C.NUMBER'),
                          ('C.ADD', 'C.COUNT')})
        self.assertEqual(affected_dependency_closure(candidate, ('C.COUNT',)),
                         ('C.ADD', 'C.COUNT', 'C.NUMBER'))
        illegal = replace(candidate, nodes=(*compiled.nodes, count, replace(
            number, stage=0), add))
        with self.assertRaisesRegex(ValueError, 'DEPENDENCY_NOT_EARLIER_STAGE'):
            dependency_coverage_plan(illegal)

    def test_dependency_change_regenerates_transitive_dependents_only(self):
        ast = compile_ast(self.course)
        b = replace(ast.nodes[0], id='B.SYNTHETIC', grade='B',
                    requires=('A.EDGE',))
        c = replace(ast.nodes[0], id='C.SYNTHETIC', grade='C',
                    requires=('B.SYNTHETIC',))
        expanded = replace(ast, nodes=(*ast.nodes, b, c))
        self.assertEqual(affected_dependency_closure(expanded, ('A.EDGE',)),
                         ('A.EDGE', 'B.SYNTHETIC', 'C.SYNTHETIC'))
        self.assertEqual(affected_dependency_closure(expanded, ('A.MAPS',)),
                         ('A.MAPS',))
        self.assertEqual(affected_dependency_closure(expanded, ('B.SYNTHETIC',)),
                         ('B.SYNTHETIC', 'C.SYNTHETIC'))
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_CHANGED_SEMANTIC_ID'):
            affected_dependency_closure(expanded, ('C.UNKNOWN',))

    def test_source_interpreters_materialize_actual_unreleased_probes(self):
        root = Path(__file__).resolve().parents[3] / 'vendor' / 'legacy-v16'
        if not root.is_dir():
            self.skipTest('Pinned source absent')
        micro, development, graph, _, _ = read_sources(root)
        ast = compile_ast(self.course)
        planned = compile_probe_plan(ast)
        registry = json.loads((Path(__file__).resolve().parents[3] /
                   'docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json').read_text())
        exam_ids = {r['id'] for r in registry['examination_rows']}
        actual = materialize_probes(planned, micro=micro, development=development,
                                    graph=graph, excluded_record_ids=exam_ids)
        self.assertEqual(len(actual), 96)
        self.assertEqual(len({r['record_id'] for r in actual}), 96)
        self.assertFalse({r['record_id'] for r in actual} & exam_ids)
        self.assertTrue(all(not r['admitted'] for r in actual))
        self.assertEqual(actual, materialize_probes(planned, micro=micro,
                 development=development, graph=graph, excluded_record_ids=exam_ids))

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


if __name__ == '__main__':
    unittest.main()
