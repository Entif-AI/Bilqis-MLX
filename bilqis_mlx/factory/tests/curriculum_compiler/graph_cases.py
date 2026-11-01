import json
from dataclasses import replace
from pathlib import Path
from bilqis_mlx.curriculum_compiler import (
    compile_ast, compile_probe_plan, diagnose_coverage,
    dependency_coverage_plan, affected_dependency_closure,
)

class GraphProbeCases:
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
