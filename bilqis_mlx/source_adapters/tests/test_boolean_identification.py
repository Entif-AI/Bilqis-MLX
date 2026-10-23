"""Contract tests for inverse Boolean primitive identification in Grade B."""
from collections import Counter
import json
import os
from pathlib import Path
import unittest

from bilqis_mlx.boolean_composite import build_course as build_composite
from bilqis_mlx.boolean_identification import (
    ANSWER_KIND, ASSESSMENT_ITEMS, CAPABILITY, GENERATOR, ORACLE, RELEASE,
    answer_heads, build_course, draw_identification, encode_record,
)
from bilqis_mlx.boolean_identification_oracle import evaluate as independent_evaluate
from bilqis_mlx.curriculum import BOOLEAN_OPERATORS
from bilqis_mlx.factory.generation import draw_release_rows
from bilqis_mlx.factory.live_releases import initial_course, boolean_successor
from bilqis_mlx.factory.release import compile_factory_release
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.grade_c_preflight import qualify as qualify_grade_c
from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.diagnostics.teaching import inspect_lesson_step
from bilqis_mlx.typed_answer_training import prepare_typed_batches


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "vendor" / "legacy-v16"
MANIFEST = ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"


@unittest.skipUnless(
    os.environ.get("BILQIS_FULL_GRADE_B_TESTS") == "1" and
    (SOURCE / "bilqis_micro/kernel.py").is_file(),
    "legacy/full Grade B compatibility tests are opt-in")
class BooleanIdentificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        accepted = accepted_grade_a(json.loads(MANIFEST.read_text()))
        cls.a = initial_course(accepted)
        cls.b = boolean_successor(cls.a, SOURCE)
        cls.composite = build_composite(cls.b, SOURCE)
        cls.course = build_course(cls.composite, SOURCE)
        cls.micro, _, cls.graph, _, _ = read_sources(SOURCE)

    def test_release_adds_eighth_derived_capability_without_new_semantic_root(self):
        grade = self.course.grades[-1]
        cap = grade.capabilities[-1]
        roots = tuple("cogal.operator." + op for op in BOOLEAN_OPERATORS)
        self.assertEqual(self.course.version, RELEASE)
        self.assertEqual(len(grade.capabilities), 8)
        self.assertEqual(cap.id, CAPABILITY)
        self.assertEqual(cap.taught_roots, roots)
        self.assertEqual(cap.examined_roots, roots)
        self.assertEqual(cap.prerequisites, ())
        self.assertEqual(cap.composed_of, ())
        self.assertEqual(cap.answer_families[0].kind, ANSWER_KIND)
        self.assertEqual(cap.answer_families[0].values, BOOLEAN_OPERATORS)
        self.assertEqual(len(cap.answer_families), 1)
        self.assertEqual(cap.lesson_generator, GENERATOR)
        self.assertEqual(cap.independent_oracle, ORACLE)
        self.assertEqual(dict(grade.exam_item_counts)[CAPABILITY], ASSESSMENT_ITEMS)

    def test_twelve_rows_balance_six_operator_targets_and_hide_gold_operator(self):
        rows = draw_identification(SOURCE, self.graph, seed=2026101902)
        self.assertEqual(len(rows), 12)
        self.assertEqual(len({row["id"] for row in rows}), 12)
        self.assertEqual(Counter(row["gold"] for row in rows),
                         Counter({op: 2 for op in BOOLEAN_OPERATORS}))
        self.assertNotEqual(rows, draw_identification(SOURCE, self.graph, seed=2026101903))
        for row in rows:
            with self.subTest(operator=row["gold"], row=row["id"][:8]):
                self.assertEqual(row["capability"], CAPABILITY)
                self.assertEqual(row["answer_kind"], ANSWER_KIND)
                self.assertEqual(row["operator_options"], list(BOOLEAN_OPERATORS))
                self.assertEqual(row["gold"], independent_evaluate(row["record"]))
                self.assertEqual(row["tokens"], encode_record(row["record"], SOURCE, self.graph))
                self.assertNotIn(
                    self.graph["tokens"].index("cogal.operator." + row["gold"]),
                    row["tokens"],
                )
                self.assertTrue(1 <= len(row["tokens"]) <= 96)

    def test_each_question_exposes_same_shape_complete_truth_signature(self):
        rows = draw_identification(SOURCE, self.graph, seed=41)
        for row in rows:
            observations = row["record"]["observations"]
            self.assertEqual({len(observation["operands"])
                              for observation in observations}, {2})
            self.assertNotIn("world", row["record"])
            patterns = {
                tuple(operand["value"] for operand in observation["operands"])
                for observation in observations
            }
            expected = {(False, False), (False, True), (True, False), (True, True)}
            self.assertEqual(patterns, expected)
            self.assertEqual(len(observations), len(expected))

    def test_all_six_operator_signatures_are_unique_without_arity_signal(self):
        rows = draw_identification(SOURCE, self.graph, seed=73)
        signatures = {}
        for row in rows:
            if row["gold"] in signatures:
                continue
            ordered = sorted(
                (tuple(operand["value"] for operand in observation["operands"]),
                 observation["result"])
                for observation in row["record"]["observations"])
            signatures[row["gold"]] = tuple(result for _, result in ordered)
        self.assertEqual(set(signatures), set(BOOLEAN_OPERATORS))
        self.assertEqual(len(set(signatures.values())), len(BOOLEAN_OPERATORS))

    def test_factory_uses_one_adapter_and_generates_ninety_six_b_rows(self):
        registry = live_source_registry()
        release = compile_factory_release(self.course, registry)
        definitions = [item for item in release.capabilities if item.grade_id == "B"]
        self.assertEqual(len({item.source_adapter_id for item in definitions}), 1)
        rows = draw_release_rows(SOURCE, self.graph, release, registry, seed=29)
        counts = Counter(row["capability"] for row in rows)
        self.assertEqual(len(rows), 168)
        self.assertEqual(sum(count for cap, count in counts.items() if cap.startswith("B.")), 96)
        self.assertEqual(counts[CAPABILITY], 12)
        self.assertEqual({counts["B." + op] for op in BOOLEAN_OPERATORS}, {12})
        self.assertEqual(counts["B.COMPOSITE"], 12)

    def test_six_way_answer_head_reuses_existing_operator_token_ids(self):
        heads = answer_heads(self.graph)
        head = heads[ANSWER_KIND]
        self.assertEqual(head["values"], list(BOOLEAN_OPERATORS))
        self.assertEqual(head["token_ids"], [
            self.graph["tokens"].index("cogal.operator." + op)
            for op in BOOLEAN_OPERATORS
        ])
        self.assertTrue(all(index < len(self.graph["tokens"])
                            for index in head["token_ids"]))

    def test_actual_generated_rows_bind_to_the_six_way_typed_batch(self):
        rows = list(draw_identification(SOURCE, self.graph, seed=89))
        batches = prepare_typed_batches(rows, answer_heads(self.graph))
        self.assertEqual(set(batches), {ANSWER_KIND})
        batch = batches[ANSWER_KIND]
        self.assertEqual(len(batch["row_ids"]), 12)
        self.assertEqual(len(batch["answer_ids"]), 6)
        self.assertEqual(Counter(batch["gold_labels"]),
                         Counter({op: 2 for op in BOOLEAN_OPERATORS}))

    def test_inverse_rows_remain_legible_to_teaching_diagnostics(self):
        rows = list(draw_identification(SOURCE, self.graph, seed=137))
        evidence = inspect_lesson_step(self.course, CAPABILITY, rows, rows[:4])
        self.assertEqual(evidence.offered_count, 12)
        self.assertEqual(evidence.delivered_count, 4)
        self.assertEqual(evidence.prerequisite_capabilities, ())

    def test_grade_c_preflight_requires_full_168_item_idboolops_parent(self):
        manifest = json.loads(MANIFEST.read_text())
        report = qualify_grade_c(SOURCE, manifest, previous=self.course)
        self.assertEqual(report["pre_c_cumulative_items"], 168)
        self.assertEqual(
            report["runtime_admission"],
            "ONE_COMPLETE_CUMULATIVE_A_B_168_OF_168_CHECKPOINT_THEN_HUMAN_RESUME",
        )


if __name__ == "__main__":
    unittest.main()
