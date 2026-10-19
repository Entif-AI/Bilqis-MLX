"""Read-only source witness and multi-grade curriculum validation for Grade B."""
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.curriculum import ExamItem, validate_exam_item
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.grade_b_oracle import CONNECTIVES, evaluate as independent_oracle
from bilqis_mlx.live_grade_a import live_course as live_a_course
from bilqis_mlx.live_grade_b import (GENERATOR, RELEASE, draw_connectives,
                                    live_course, constructor_digest, source_attestation)

ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / "vendor" / "legacy-v16"
MANIFEST = ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"


@unittest.skipUnless((LEGACY / "bilqis_micro/kernel.py").is_file(),
                     "Pinned predecessor source is not mounted")
class LiveGradeBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.micro, cls.development, cls.graph, _, _ = read_sources(LEGACY)
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.grade_a = live_a_course(accepted_grade_a(manifest))
        cls.course = live_course(cls.grade_a, LEGACY)

    def test_six_real_source_connectives_have_legal_predecessor_prerequisites(self):
        self.assertEqual(tuple(c.id for c in self.course.grades[1].capabilities),
                         tuple("B." + name for name in CONNECTIVES))
        self.assertEqual(self.course.grades[0], self.grade_a.grades[0])
        self.assertEqual(self.course.version, RELEASE)
        self.assertFalse(self.course.program_complete)
        self.assertTrue(self.course.executable)
        self.assertEqual(len(constructor_digest()), 64)
        self.assertEqual(source_attestation(LEGACY)["semantic_mode"],
                         "PINNED_TYPED_FORMAL_ADAPTER_NOT_NI_WORDFORM")
        for cap in self.course.grades[1].capabilities:
            self.assertEqual(cap.prerequisites,
                             ("A.IDENTITY", "A.PARENT", "A.LINK"))
            self.assertEqual(cap.answer_families[0].kind, "binary")

    def test_full_seventy_two_is_seeded_balanced_source_oracle_agreed(self):
        rows = draw_connectives(LEGACY, self.graph, seed=2026101507)
        self.assertEqual(rows, draw_connectives(LEGACY, self.graph, seed=2026101507))
        self.assertNotEqual(rows, draw_connectives(LEGACY, self.graph, seed=2026101508))
        self.assertEqual(len(rows), 72)
        self.assertEqual(len({r["id"] for r in rows}), 72)
        self.assertEqual(Counter(r["capability"] for r in rows),
                         Counter({"B." + op:12 for op in CONNECTIVES}))
        for op in CONNECTIVES:
            subset = [r for r in rows if r["capability"] == "B." + op]
            self.assertEqual(Counter(r["gold"] for r in subset),
                             Counter({"TRUE":6, "FALSE":6}))
            self.assertEqual({r["universe_size"] for r in subset}, {3,4})
            self.assertEqual({r["record"]["query"]["operator"] for r in subset}, {op})
            for r in subset:
                self.assertEqual(r["gold"], self.micro.evaluate(r["record"]))
                self.assertEqual(r["gold"], self.micro.independent_evaluate(r["record"]))
                self.assertEqual(r["gold"], independent_oracle(r["record"],r["capability"]))
                self.assertEqual(tuple(r["tokens"]),tuple(self.micro.encode(r["record"])))
                self.assertLessEqual(max(r["tokens"]), 221)
                self.assertGreaterEqual(min(r["tokens"]), 0)
                validate_exam_item(self.course, "B", ExamItem(
                    r["capability"], "binary", r["gold"],
                    (r["root"],), (), r["oracle"], r["id"]),
                    mastered_grade_ids=("A",))

    def test_one_capability_draws_extra_optimizer_batches_without_embargo(self):
        first = draw_connectives(LEGACY,self.graph,seed=413,each=32,capability="B.AND")
        next_step = draw_connectives(LEGACY,self.graph,seed=414,each=32,capability="B.AND")
        self.assertEqual(len(first),32)
        self.assertTrue(all(r["capability"] == "B.AND" for r in first))
        self.assertEqual(Counter(r["gold"] for r in first), Counter({"TRUE":16,"FALSE":16}))
        self.assertNotEqual({r["id"] for r in first}, {r["id"] for r in next_step})
        self.assertEqual(first, draw_connectives(LEGACY,self.graph,seed=413,
                                                 each=32,capability="B.AND"))

    def test_oracle_rejects_undeclared_operator_and_wrong_arity(self):
        row = draw_connectives(LEGACY,self.graph,seed=1,each=4,capability="B.NOT")[0]
        with self.assertRaisesRegex(ValueError,"UNKNOWN_TASK"):
            independent_oracle(row["record"],"B.XNOR")
        wrong = json.loads(json.dumps(row["record"]))
        wrong["query"]["operator"] = "AND"
        with self.assertRaisesRegex(ValueError,"CONNECTIVE_SHAPE"):
            independent_oracle(wrong,"B.NOT")
        wrong["query"]["operator"] = "NOT"
        wrong["query"]["args"] = []
        with self.assertRaisesRegex(ValueError,"CONNECTIVE_SHAPE"):
            independent_oracle(wrong,"B.NOT")

    def test_b_refuses_predecessor_grade_a_drift_or_unpinned_vocab(self):
        changed = replace(self.grade_a, grades=(replace(self.grade_a.grades[0],
                            assessment_sha256="f"*64),))
        self.assertNotEqual(live_course(changed,LEGACY).grades[1].assessment_sha256,
                            self.course.grades[1].assessment_sha256)
        with self.assertRaisesRegex(ValueError,"PREDECESSOR"):
            live_course(replace(self.grade_a, program_complete=True),LEGACY)
        swapped = dict(self.graph)
        swapped["tokens"] = list(swapped["tokens"])
        swapped["tokens"][5] = "ATTACKER-UNKNOWN-TOKEN"
        with self.assertRaisesRegex(ValueError,"PREFIX"):
            draw_connectives(LEGACY,swapped,seed=1,each=4)


if __name__ == "__main__":
    unittest.main()
