"""Read-only source witness and multi-grade curriculum validation for Grade B."""
from collections import Counter
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.curriculum import ExamItem, validate_exam_item
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.grade_b_oracle import CONNECTIVES, evaluate as independent_oracle
from bilqis_mlx.live_grade_a import live_course as live_a_course
from bilqis_mlx.live_grade_b import (
    GENERATOR, RELEASE, _encode_connective_record, _encode_logic_record,
    _logic_source, _u7c_pattern_counts, draw_connectives, live_course,
    constructor_digest, source_attestation,
)
from bilqis_mlx.source_adapters.school import draw_b

ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / "vendor" / "legacy-v16"
MANIFEST = ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"


@unittest.skipUnless(
    os.environ.get("BILQIS_FULL_GRADE_B_TESTS") == "1" and
    (LEGACY / "bilqis_micro/kernel.py").is_file(),
    "legacy/full Grade B compatibility tests are opt-in")
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
                         "DIRECT_TYPED_BOOLEAN_AST")
        for cap in self.course.grades[1].capabilities:
            self.assertEqual(cap.prerequisites, ())
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
            self.assertTrue(all("world" not in r["record"] for r in subset))
            self.assertEqual({r["record"]["task"] for r in subset}, {"evaluate"})
            self.assertEqual({r["record"]["expression"]["operator"] for r in subset}, {op})
            logic = _logic_source(LEGACY)
            for r in subset:
                self.assertEqual(r["gold"], independent_oracle(r["record"],r["capability"]))
                self.assertEqual(
                    r["tokens"],
                    _encode_connective_record(
                        logic, r["record"], self.graph, r["capability"]))
                self.assertLess(max(r["tokens"]), len(self.graph["tokens"]))
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

    def test_row_identity_is_capability_scoped_while_source_identity_is_record_scoped(self):
        row = draw_connectives(
            LEGACY, self.graph, seed=2026102310, each=12,
            capability="B.AND")[0]
        canonical = lambda value: json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False).encode()
        source_id = hashlib.sha256(canonical(row["record"])).hexdigest()
        row_id = hashlib.sha256(canonical([
            row["capability"], row["record"]])).hexdigest()
        self.assertEqual(row["source_id"], source_id)
        self.assertEqual(row["id"], row_id)
        self.assertNotEqual(row["id"], row["source_id"])

    def test_factory_runtime_uses_u7c_balanced_truth_cells(self):
        for seed in range(20):
            for op in CONNECTIVES:
                capability = "B." + op
                rows = draw_b(source_root=LEGACY, graph=self.graph, course=self.course,
                              capability=capability, seed=seed, each=12)
                self.assertEqual(len(rows), 12)
                self.assertEqual(Counter(r["gold"] for r in rows),
                                 Counter({"TRUE": 6, "FALSE": 6}))
                self.assertEqual(
                    Counter(tuple(r["operand_truths"]) for r in rows),
                    Counter(_u7c_pattern_counts(op, 12)))
                self.assertEqual({r["runtime_sampler"] for r in rows},
                                 {"bilqis.mlx.grade-b-u7c-runtime-sampler/v3"})

    def test_and_and_implies_cover_all_truth_cells_with_named_outer_operands(self):
        expected = {
            "B.AND": Counter({
                (True, True): 6,
                (True, False): 2,
                (False, True): 2,
                (False, False): 2,
            }),
            "B.IMPLIES": Counter({
                (True, False): 6,
                (True, True): 2,
                (False, False): 2,
                (False, True): 2,
            }),
        }
        for capability, pattern_counts in expected.items():
            logic = _logic_source(LEGACY)
            rows = draw_connectives(
                LEGACY, self.graph, seed=2026102502, each=12,
                capability=capability)
            self.assertEqual(
                Counter(tuple(row["operand_truths"]) for row in rows),
                pattern_counts)
            self.assertEqual(
                Counter(row["gold"] for row in rows),
                Counter({"TRUE": 6, "FALSE": 6}))
            operator = capability.removeprefix("B.")
            for row in rows:
                self.assertEqual(
                    row["record"].get("presentation"),
                    "named-outer-operands/v1")
                names = [self.graph["tokens"][token] for token in row["tokens"]]
                self.assertEqual(names[:5], [
                    "task.evaluate",
                    "cogal.operator." + operator,
                    "micro.proof.premise",
                    "cogal.variable.P",
                    "syntax.bind",
                ])
                separator = names.index("syntax.separator")
                self.assertEqual(
                    names[separator + 1:separator + 4],
                    ["micro.proof.premise", "cogal.variable.Q", "syntax.bind"])
                self.assertEqual(names[-1], "syntax.end")
                self.assertEqual(
                    set(row["record"]["assignments"]),
                    logic.free_variables(row["record"]["expression"]))
            self.assertTrue(any(row["record"]["assignments"] for row in rows))

    def test_other_atomic_connectives_keep_the_historical_logic_codec(self):
        logic = _logic_source(LEGACY)
        for capability in ("B.NOT", "B.OR", "B.XOR", "B.IFF"):
            row = draw_connectives(
                LEGACY, self.graph, seed=2026102503, each=12,
                capability=capability)[0]
            self.assertNotIn("presentation", row["record"])
            self.assertEqual(
                row["tokens"],
                _encode_logic_record(logic, row["record"], self.graph))

    def test_pre_landmark_and_implies_records_keep_the_historical_codec(self):
        logic = _logic_source(LEGACY)
        for operator in ("AND", "IMPLIES"):
            expression = logic.apply(
                operator, logic.variable("P"), logic.variable("Q"))
            record = logic.evaluation_record(
                expression, {"P": True, "Q": False})
            self.assertEqual(
                _encode_connective_record(
                    logic, record, self.graph, "B." + operator),
                _encode_logic_record(logic, record, self.graph))
            self.assertEqual(
                independent_oracle(record, "B." + operator),
                "FALSE")

    def test_small_balanced_and_implies_draws_remain_supported(self):
        for capability in ("B.AND", "B.IMPLIES"):
            rows = draw_connectives(
                LEGACY, self.graph, seed=2026102506, each=4,
                capability=capability)
            self.assertEqual(len(rows), 4)
            self.assertEqual(
                Counter(row["gold"] for row in rows),
                Counter({"TRUE": 2, "FALSE": 2}))

    def test_oracle_rejects_undeclared_operator_and_wrong_arity(self):
        row = draw_connectives(LEGACY,self.graph,seed=1,each=4,capability="B.NOT")[0]
        with self.assertRaisesRegex(ValueError,"UNKNOWN_TASK"):
            independent_oracle(row["record"],"B.XNOR")
        wrong = json.loads(json.dumps(row["record"]))
        wrong["expression"]["operator"] = "AND"
        with self.assertRaisesRegex(ValueError,"CONNECTIVE_SHAPE"):
            independent_oracle(wrong,"B.NOT")
        wrong["expression"]["operator"] = "NOT"
        wrong["expression"]["args"] = []
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
