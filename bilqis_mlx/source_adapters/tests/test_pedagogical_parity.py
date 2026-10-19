"""Predecessor-derived curriculum tests, with no model or optimizer writes."""

from copy import deepcopy
from pathlib import Path
import unittest

from bilqis_mlx.pedagogical_parity import (
    audit_summary, build_plan, eligible_stage, head_bindings,
    predecessor_instruction_choice, predecessor_teaching_batch, validate_plan,
)


LEGACY = Path(__file__).resolve().parents[3] / "vendor" / "legacy-v16"


class PredecessorPedagogyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = build_plan(LEGACY)

    def test_atomic_number_answers_precede_composed_arithmetic(self):
        units = self.plan["stages"]["NUMERAL_IDENTITY"]["train"]
        self.assertEqual([r["gold"] for r in units], ["0", "1", "2", "3"])
        self.assertTrue(all(r["answer_kind"] == "numeric_0_3" for r in units))
        self.assertEqual(eligible_stage(self.plan, "DIRECT_ARITHMETIC", {}), False)
        self.assertEqual(eligible_stage(self.plan, "TRUTH_CONTRAST", {}), False)

    def test_exact_predecessor_20_expression_split_and_training_replay(self):
        plan = self.plan
        self.assertEqual({p: len(plan["pairs"][p]) for p in
                          ("train", "development", "sealed")},
                         {"train": 12, "development": 4, "sealed": 4})
        self.assertEqual({r["source_id"] for r in plan["stages"]["DIRECT_ARITHMETIC"]["replay"]},
                         {r["source_id"] for r in plan["stages"]["DIRECT_ARITHMETIC"]["train"]
                          if r["source"] in plan["core_sources"]})
        for stage in ("DIRECT_ARITHMETIC", "TRUTH_CONTRAST"):
            ids = {r["id"] for r in plan["stages"][stage]["train"]}
            self.assertTrue({r["id"] for r in plan["stages"][stage]["replay"]} <= ids)
        self.assertEqual({r["gold"] for r in plan["stages"]["DIRECT_ARITHMETIC"]["replay"]},
                         {"0", "1", "2", "3"})

    def test_each_semantic_source_has_direct_value_and_both_truth_contrasts(self):
        for partition, pairs in self.plan["pairs"].items():
            for pair in pairs:
                with self.subTest(partition=partition, source=pair["source"]):
                    direct, positive, negative = pair["rows"]
                    self.assertEqual([r["answer_kind"] for r in pair["rows"]],
                                     ["numeric_0_3", "evidence", "evidence"])
                    self.assertEqual((positive["gold"], negative["gold"]),
                                     ("TRUE", "FALSE"))
                    self.assertEqual(direct["gold"], str(pair["value"]))
                    native = direct["native_output"]
                    self.assertEqual(native["identity"],
                                     "school.number." + direct["gold"])
                    self.assertEqual(native["token_id"],
                        self.plan["heads"]["semantic_token"]["values"].index(native["identity"]))
                    self.assertEqual(len({r["source_id"] for r in pair["rows"]}), 1)
                    self.assertEqual(len({r["id"] for r in pair["rows"]}), 3)

    def test_no_exam_source_is_acquired_by_accident(self):
        owners = {}
        for partition, pairs in self.plan["pairs"].items():
            for pair in pairs:
                self.assertNotIn(pair["source_id"], owners)
                owners[pair["source_id"]] = partition
        self.assertEqual(len(owners), 20)
        self.assertFalse(self.plan["training_authorized"])
        self.assertFalse(self.plan["qualification_authorized"])
        self.assertEqual(self.plan["sealed_exam_policy"], "RESERVED_NOT_USED_FOR_SELECTION")

    def test_wrong_numeric_gold_binary_gold_and_missing_negative_fail(self):
        for change in ("numeric", "boolean", "negative"):
            with self.subTest(change=change):
                altered = deepcopy(self.plan)
                pair = altered["pairs"]["train"][0]
                if change == "numeric":
                    pair["rows"][0]["gold"] = "3" if pair["value"] != 3 else "2"
                elif change == "boolean":
                    pair["rows"][2]["gold"] = "TRUE"
                else:
                    pair["rows"].pop()
                with self.assertRaisesRegex(ValueError, "PARITY_"):
                    validate_plan(altered, LEGACY)

    def test_training_replay_with_unseen_question_is_rejected(self):
        altered = deepcopy(self.plan)
        altered["stages"]["DIRECT_ARITHMETIC"]["replay"][0]["id"] = "unknown-id"
        with self.assertRaisesRegex(ValueError, "PARITY_"):
            validate_plan(altered, LEGACY)

    def test_existing_numeric_readout_classes_and_full_101_diagnostic(self):
        mapping = head_bindings(self.plan)
        self.assertEqual(mapping["numeric_0_3"]["values"], ["0", "1", "2", "3"])
        self.assertEqual(len(mapping["numeric_full_101"]["token_ids"]), 101)
        self.assertEqual(len(mapping["evidence"]["token_ids"]), 5)
        self.assertEqual(len(set(mapping["numeric_full_101"]["token_ids"])), 101)
        self.assertEqual(mapping["numeric_0_3"]["token_ids"],
                         mapping["numeric_full_101"]["token_ids"][:4])
        self.assertEqual(mapping["semantic_token"]["token_ids"],list(range(222)))
        self.assertEqual([mapping["semantic_token"]["values"][i]
                          for i in mapping["numeric_full_101"]["token_ids"]],
                         ["school.number." + str(i) for i in range(101)])

    def test_stage_gate_requires_measured_exposed_acquisition_and_source_identity(self):
        stage = self.plan["stages"]["NUMERAL_IDENTITY"]
        observed = {"NUMERAL_IDENTITY": {"status": "ACQUIRED_ON_EXPOSED_REPLAY",
                    "correct": 4, "total": 4,
                    "probe_ids": [r["id"] for r in stage["replay"]],
                    "source_sha256": self.plan["source_sha256"],
                    "student_sha256": "a" * 64, "optimizer_step": 2}}
        self.assertTrue(eligible_stage(self.plan, "DIRECT_ARITHMETIC", observed))
        self.assertFalse(eligible_stage(self.plan, "TRUTH_CONTRAST", observed))
        changed = deepcopy(observed)
        changed["NUMERAL_IDENTITY"]["correct"] = 3
        self.assertFalse(eligible_stage(self.plan, "DIRECT_ARITHMETIC", changed))

    def test_operator_report_exposes_known_direct_and_false_pair_but_not_sealed_gold(self):
        report = audit_summary(self.plan)
        self.assertEqual(report["example"], {"source": "ADD(1,2)",
                         "direct": "3", "native_output_identity": "school.number.3",
                         "native_output_token_id": self.plan["heads"]["numeric_0_3"]["token_ids"][3],
                         "correct_claim": "TRUE",
                         "incorrect_claim": "FALSE"})
        self.assertEqual(report["source_partitions"],
                         {"train": 12, "development": 4, "sealed": 4})
        self.assertFalse(report["qualification_authorized"])
        self.assertNotIn("rows", report)

    def test_reuses_original_48_row_teacher_strategy_and_exact_replay(self):
        for method in ("standard", "structural_equivalence",
                       "minimal_counterfactual"):
            with self.subTest(method=method):
                batch = predecessor_teaching_batch(
                    LEGACY, grade="B01", seed=2001, method=method)
                rows = batch["rows"]
                self.assertEqual(len(rows), 48)
                self.assertEqual(batch["allocation"],
                    {"current": 42, "random_old": 6, "preview": 0})
                self.assertEqual(sum(r["answer_kind"] == "numeric_0_3"
                                     for r in rows), 6)
                self.assertEqual(sum(bool(r.get("native_output")) for r in rows),6)
                self.assertEqual(sum(r["answer_kind"] == "evidence"
                                     for r in rows), 42)
                self.assertEqual(len({r["id"] for r in rows}), 48)
                self.assertEqual(len([r for r in rows
                    if r["tranche"] == "random_old"]), 6)
                self.assertTrue(set(batch["replay_ids"]) <=
                                {r["id"] for r in rows})
                self.assertEqual(set(batch["replay_ids"][:4]),
                                 {r["id"] for r in self.plan["stages"][
                                      "DIRECT_ARITHMETIC"]["replay"]})
                self.assertTrue({r["id"] for r in self.plan["stages"][
                                    "TRUTH_CONTRAST"]["replay"]} <=
                                set(batch["replay_ids"]))

    def test_original_instruction_bandit_is_callable_without_mutating_teacher(self):
        teacher = {"numeric_instruction_methods": {"B01": {
            key: {"trials": 1, "reward_sum": value, "reward_ema": value}
            for key,value in (("standard", -10.),
                              ("minimal_counterfactual", 12.),
                              ("structural_equivalence", -9.))}}}
        before = deepcopy(teacher)
        selected = predecessor_instruction_choice(LEGACY, teacher, grade="B01",seed=9)
        self.assertEqual(selected, "minimal_counterfactual")
        self.assertEqual(teacher, before)


if __name__ == "__main__":
    unittest.main()
