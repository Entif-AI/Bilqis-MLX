"""Contract tests for the user-approved B.COMPOSITE derived capability."""
from collections import Counter
import json
import os
from pathlib import Path
import unittest

from bilqis_mlx.boolean_composite import (
    CAPABILITY, GENERATOR, ORACLE, RELEASE, build_course, draw_composite,
    independent_evaluate,
)
from bilqis_mlx.factory.generation import draw_release_rows
from bilqis_mlx.factory.live_releases import initial_course, boolean_successor
from bilqis_mlx.factory.release import compile_factory_release
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.grade_b_oracle import CONNECTIVES
from bilqis_mlx.live_grade_b import _encode_logic_record, _logic_source
from bilqis_mlx.diagnostics.teaching import inspect_lesson_step
from bilqis_mlx.source_adapters.school import live_source_registry


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "vendor" / "legacy-v16"
MANIFEST = ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"


@unittest.skipUnless(
    os.environ.get("BILQIS_FULL_GRADE_B_TESTS") == "1" and
    (SOURCE / "bilqis_micro/kernel.py").is_file(),
    "legacy/full Grade B compatibility tests are opt-in")
class BooleanCompositeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        accepted = accepted_grade_a(json.loads(MANIFEST.read_text()))
        cls.a = initial_course(accepted)
        cls.b = boolean_successor(cls.a, SOURCE)
        cls.course = build_course(cls.b, SOURCE)
        cls.micro, _, cls.graph, _, _ = read_sources(SOURCE)

    def test_release_adds_one_derived_capability_without_new_semantic_root(self):
        grade = self.course.grades[-1]
        cap = grade.capabilities[-1]
        roots = tuple("cogal.operator." + op for op in CONNECTIVES)
        self.assertEqual(self.course.version, RELEASE)
        self.assertEqual(tuple(c.id for c in grade.capabilities)[-1], CAPABILITY)
        self.assertEqual(len(grade.capabilities), 7)
        self.assertEqual(cap.taught_roots, roots)
        self.assertEqual(cap.examined_roots, roots)
        self.assertEqual(cap.prerequisites, ())
        self.assertEqual(cap.composed_of, ())
        self.assertEqual(cap.lesson_generator, GENERATOR)
        self.assertEqual(cap.independent_oracle, ORACLE)
        self.assertEqual(dict(grade.exam_item_counts)[CAPABILITY], 12)
        self.assertEqual(grade.teaching_stages, ())

    def test_exact_shuffle_partition_process_has_equal_operator_representation(self):
        rows = draw_composite(SOURCE, self.graph, seed=2026101901, each=12)
        self.assertEqual(rows, draw_composite(SOURCE, self.graph, seed=2026101901, each=12))
        self.assertNotEqual(rows, draw_composite(SOURCE, self.graph, seed=2026101902, each=12))
        self.assertEqual(Counter(row["composition_width"] for row in rows),
                         Counter({2: 6, 3: 6}))
        appearances = Counter(op for row in rows for op in row["operators"])
        self.assertEqual(appearances, Counter({op: 5 for op in CONNECTIVES}))
        for start in (0, 3):
            self.assertEqual({op for row in rows[start:start + 3] for op in row["operators"]},
                             set(CONNECTIVES))
        for start in (6, 8, 10):
            self.assertEqual({op for row in rows[start:start + 2] for op in row["operators"]},
                             set(CONNECTIVES))

    def test_nested_rows_are_source_grounded_and_three_oracle_agreed(self):
        rows = draw_composite(SOURCE, self.graph, seed=17, each=12)
        self.assertEqual(len(rows), 12)
        self.assertEqual(len({row["id"] for row in rows}), 12)
        for row in rows:
            self.assertEqual(row["capability"], CAPABILITY)
            self.assertEqual(row["generator"], GENERATOR)
            self.assertEqual(row["oracle"], ORACLE)
            self.assertNotIn("world", row["record"])
            self.assertEqual(row["record"]["task"], "evaluate")
            self.assertEqual(row["gold"], independent_evaluate(row["record"]))
            logic = _logic_source(SOURCE)
            self.assertEqual(row["tokens"], _encode_logic_record(logic, row["record"], self.graph))
            self.assertTrue(1 <= len(row["tokens"]) <= 96)
            self.assertEqual(len(row["operators"]), row["composition_width"])

    def test_answer_balance_varies_without_returning_to_six_six(self):
        balances = set()
        for seed in range(20):
            rows = draw_composite(SOURCE, self.graph, seed=seed, each=12)
            true_count = sum(row["gold"] == "TRUE" for row in rows)
            balances.add(true_count)
            self.assertIn(true_count, {4, 5, 7, 8})
        self.assertGreater(len(balances), 1)

    def test_factory_generates_eighty_four_b_rows_inside_cumulative_release(self):
        registry = live_source_registry()
        release = compile_factory_release(self.course, registry)
        rows = draw_release_rows(SOURCE, self.graph, release, registry, seed=29)
        counts = Counter(row["capability"] for row in rows)
        b_rows = [row for row in rows if row["capability"].startswith("B.")]
        self.assertEqual(len(rows), 156)
        self.assertEqual(len(b_rows), 84)
        self.assertEqual(counts[CAPABILITY], 12)
        self.assertEqual({counts["B." + op] for op in CONNECTIVES}, {12})

    def test_shared_boolean_roots_remain_legible_to_teaching_diagnostics(self):
        registry = live_source_registry()
        release = compile_factory_release(self.course, registry)
        composite = draw_release_rows(
            SOURCE, self.graph, release, registry, seed=37,
            capability=CAPABILITY, each=12)
        evidence = inspect_lesson_step(self.course, CAPABILITY, composite, composite[:4])
        self.assertEqual(evidence.offered_count, 12)
        self.assertEqual(evidence.delivered_count, 4)
        atomic = draw_release_rows(
            SOURCE, self.graph, release, registry, seed=38,
            capability="B.AND", each=12)
        atomic_evidence = inspect_lesson_step(self.course, "B.AND", atomic, atomic[:4])
        self.assertEqual(atomic_evidence.delivered_count, 4)


if __name__ == "__main__":
    unittest.main()
