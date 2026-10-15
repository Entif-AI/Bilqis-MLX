"""Neural-inert proof that curriculum structure generates reusable probes."""
import json
from pathlib import Path
import unittest

from bilqis_mlx.curriculum_compiler import (compile_ast, compile_probe_plan,
                                          diagnose_coverage, materialize_probes)
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.grade_a_probe import read_sources


class CurriculumCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.course = accepted_grade_a(json.loads(
            (root / 'docs/GRADE_A_CANDIDATE_MANIFEST_V2.json').read_text()))

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

    def test_source_interpreters_materialize_actual_unreleased_probes(self):
        root = Path(__file__).resolve().parents[2] / 'bilqis-triplets-v16'
        if not root.is_dir():
            self.skipTest('Pinned source absent')
        micro, development, graph, _, _ = read_sources(root)
        ast = compile_ast(self.course)
        planned = compile_probe_plan(ast)
        registry = json.loads((Path(__file__).resolve().parents[1] /
                   'docs/GRADE_A_CANDIDATE_MANIFEST_V2.json').read_text())
        exam_ids = {r['id'] for r in registry['examination_rows']}
        actual = materialize_probes(planned, micro=micro, development=development,
                                    graph=graph, excluded_record_ids=exam_ids)
        self.assertEqual(len(actual), 96)
        self.assertEqual(len({r['record_id'] for r in actual}), 96)
        self.assertFalse({r['record_id'] for r in actual} & exam_ids)
        self.assertTrue(all(not r['admitted'] for r in actual))
        self.assertEqual(actual, materialize_probes(planned, micro=micro,
                 development=development, graph=graph, excluded_record_ids=exam_ids))


if __name__ == '__main__':
    unittest.main()
