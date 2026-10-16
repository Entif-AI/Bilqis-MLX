"""Complete Registry C source views, with no real neural updates."""
from collections import Counter
from dataclasses import replace
from pathlib import Path
import unittest

from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.live_grade_a import live_course as a_course
from bilqis_mlx.live_grade_b import live_course as b_course
from bilqis_mlx.live_grade_c import PLANS, draw, live_course, proposed_graph
from bilqis_mlx.pedagogical_parity import _source_stack
from bilqis_mlx.source_adapters.numeric import decode
from bilqis_mlx.semantics.numeric import evaluate
from bilqis_mlx.verification.numeric import independent_value
import json
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "bilqis-triplets-v16"


class GradeCSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, _, _, _, cls.parent, _ = _source_stack(SOURCE)
        cls.graph = proposed_graph(cls.parent)
        manifest = json.loads((ROOT / "docs/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        cls.previous = b_course(a_course(accepted_grade_a(manifest)), SOURCE)

    def test_full_staged_registry_sequence_preserves_a_b_and_old_token_contracts(self):
        course = live_course(self.previous, self.graph, maximum=10)
        self.assertTrue(course.executable)
        self.assertEqual(course.grades[:-1], self.previous.grades)
        self.assertEqual(tuple(p.lesson_id for p in PLANS),
                         ("LESSON-058", "LESSON-059", "LESSON-058", "LESSON-060",
                          "LESSON-060", "LESSON-061", "LESSON-062"))
        n = len(self.parent["tokens"])
        self.assertEqual(self.graph["tokens"][:n], self.parent["tokens"])
        self.assertEqual(self.graph["nodes"][:n], self.parent["nodes"])
        self.assertEqual(len(self.graph["tokens"])-n, 5)

    def test_all_generated_views_have_independent_gold_native_ids_and_concrete_inputs(self):
        rows = draw(self.graph, seed=19, maximum=10)
        self.assertEqual(Counter(r["capability"] for r in rows),
                         {p.capability: 33 for p in PLANS})
        by_count = [r for r in rows if r["capability"] == "C.COUNT" and r["answer_kind"] == "numeric_active"]
        self.assertEqual({r["gold"] for r in by_count}, {str(i) for i in range(11)})
        for row in rows:
            with self.subTest(capability=row["capability"], identity=row["id"]):
                expression = decode(row["record"]["symbols"])
                value = evaluate(expression)
                self.assertEqual(value, independent_value(expression))
                self.assertEqual(row["gold"], "TRUE" if value is True else "FALSE" if value is False else str(value))
                self.assertEqual(row["tokens"], [self.graph["tokens"].index(s) for s in row["record"]["symbols"]])
                if row["answer_kind"] == "numeric_active":
                    self.assertEqual(self.graph["tokens"][row["native_output"]["token_id"]],
                                     "school.number."+row["gold"])
                if row["capability"] in ("C.ADD", "C.SUB", "C.MUL", "C.DIV"):
                    self.assertIn("school.syntax.number_set", row["record"]["symbols"])

    def test_fresh_draws_have_no_instruction_exam_partition_and_new_scope_is_versioned(self):
        first = draw(self.graph, seed=10, maximum=3)
        self.assertEqual(first, draw(self.graph, seed=10, maximum=3))
        self.assertNotEqual(first, draw(self.graph, seed=11, maximum=3))
        self.assertTrue(all("partition" not in row for row in first))
        self.assertNotEqual(live_course(self.previous, self.graph, maximum=3).digest(),
                            live_course(self.previous, self.graph, maximum=10).digest())

    def test_unknown_token_or_missing_source_contract_fails_only_new_c(self):
        graph = {**self.graph, "tokens": self.parent["tokens"]}
        with self.assertRaises(ValueError):
            draw(graph, seed=19, maximum=3)
        self.assertTrue(self.previous.executable)

    def test_nontrivial_semantic_families_and_seed_changes_are_covered(self):
        first = draw(self.graph, seed=1, maximum=10)
        second = draw(self.graph, seed=2, maximum=10)
        direct = lambda rows, cap: [r for r in rows if r["capability"] == cap and
                                    r["answer_kind"] == "numeric_active"]
        self.assertTrue(any(int(r["gold"]) > 1 for r in direct(first, "C.MUL")))
        self.assertTrue(any(int(r["gold"]) > 1 for r in direct(first, "C.DIV")))
        for cap in ("C.ADD", "C.MUL", "C.DIV"):
            a, b = direct(first, cap), direct(second, cap)
            self.assertNotEqual([r["record"] for r in a], [r["record"] for r in b])
            self.assertTrue(any(len(r["witness"]["left_members"]) > 0 and
                                len(r["witness"]["right_members"]) > 0 for r in a))
        for cap in ("C.MUL", "C.DIV"):
            self.assertTrue(all("school.syntax.number_groups" in r["record"]["symbols"]
                                for r in direct(first, cap)))

    def test_swapped_or_reinterpreted_source_tokens_are_rejected(self):
        graph = deepcopy(self.graph)
        a, b = (graph["tokens"].index("school.op."+name) for name in ("ADD", "SUB"))
        graph["tokens"][a], graph["tokens"][b] = graph["tokens"][b], graph["tokens"][a]
        with self.assertRaises(ValueError):
            draw(graph, seed=19, maximum=3)
