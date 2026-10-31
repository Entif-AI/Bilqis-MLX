"""Neural-inert proof that curriculum structure generates reusable probes."""
import json
from pathlib import Path
import unittest

from bilqis_mlx.factory.tests.curriculum_compiler import graph_cases as _graph
from bilqis_mlx.factory.tests.curriculum_compiler import package_cases as _package
from bilqis_mlx.curriculum_compiler import compile_ast, compile_probe_plan, materialize_probes
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.grade_a_probe import read_sources

class CurriculumCompilerTests(_graph.GraphProbeCases, _package.TypedPackageCases, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[3]
        cls.course = accepted_grade_a(json.loads(
            (root / 'docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json').read_text()))

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


if __name__ == "__main__":
    unittest.main()
