"""Predecessor-derived curriculum tests, with no model or optimizer writes."""

from copy import deepcopy
from pathlib import Path
import unittest

from bilqis_mlx.pedagogical_parity import (
    audit_summary, build_plan, eligible_stage, head_bindings,
    predecessor_instruction_choice, predecessor_teaching_batch, validate_plan,
)


from bilqis_mlx.source_adapters.predecessor_parity.tests.fixtures import PredecessorFixture, LEGACY


class PredecessorValidationTests(PredecessorFixture):
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
