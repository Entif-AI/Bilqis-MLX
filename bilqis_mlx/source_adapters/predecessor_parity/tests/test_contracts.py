"""Observable pure contracts, separate from the unavailable historical witness."""
from copy import deepcopy
from unittest import TestCase

from bilqis_mlx.pedagogical_parity import (
    PREDECESSOR, REQUIRES, _native_output, _validate_structure,
    audit_summary, eligible_stage, head_bindings,
)
from bilqis_mlx.source_adapters.predecessor_parity.tests.contract_fixtures import contract_plan


class PredecessorContractTests(TestCase):
    def test_source_pins_and_stage_prerequisites_are_read_only(self):
        for mapping in (PREDECESSOR, REQUIRES):
            key = next(iter(mapping))
            with self.assertRaises(TypeError):
                mapping[key] = mapping[key]

    def test_literal_plan_preserves_twenty_disjoint_sources_without_admission(self):
        plan = contract_plan()
        self.assertIsNone(_validate_structure(plan))
        self.assertEqual({name: len(rows) for name, rows in plan["pairs"].items()},
                         {"train": 12, "development": 4, "sealed": 4})
        self.assertFalse(plan["training_authorized"])
        self.assertFalse(plan["qualification_authorized"])

    def test_missing_negative_wrong_gold_and_reused_source_fail_exactly(self):
        for change in ("negative", "gold", "source"):
            plan = contract_plan()
            if change == "negative":
                plan["pairs"]["train"][0]["rows"].pop()
            elif change == "gold":
                plan["pairs"]["train"][0]["rows"][2]["gold"] = "TRUE"
            else:
                plan["pairs"]["development"][0]["source_id"] = "fixture:source:0"
            message = "PARITY_SOURCE_PARTITION_LEAK" if change == "source" else "PARITY_INCOMPLETE_DIRECT_TRUTH_NEGATIVE_PAIR"
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "^" + message + "$"):
                _validate_structure(plan)

    def test_replay_must_be_previously_taught(self):
        plan = contract_plan()
        plan["stages"]["DIRECT_ARITHMETIC"]["replay"] = [{"id": "untaught"}]
        with self.assertRaisesRegex(ValueError, "^PARITY_ACQUISITION_NOT_ACTUALLY_TAUGHT$"):
            _validate_structure(plan)

    def test_stage_receipt_requires_exact_source_and_measured_replay(self):
        plan = contract_plan()
        receipt = {"status": "ACQUIRED_ON_EXPOSED_REPLAY", "correct": 4, "total": 4,
                   "probe_ids": [f"fixture:unit:{value}" for value in range(4)],
                   "source_sha256": "1" * 64, "student_sha256": "a" * 64, "optimizer_step": 2}
        self.assertTrue(eligible_stage(plan, "DIRECT_ARITHMETIC", {"NUMERAL_IDENTITY": receipt}))
        self.assertFalse(eligible_stage(plan, "TRUTH_CONTRAST", {"NUMERAL_IDENTITY": receipt}))
        for field, value in (("correct", 3), ("source_sha256", "9" * 64), ("student_sha256", "bad")):
            with self.subTest(field=field):
                self.assertFalse(eligible_stage(plan, "DIRECT_ARITHMETIC",
                                               {"NUMERAL_IDENTITY": {**receipt, field: value}}))

    def test_head_bindings_are_an_independent_copy(self):
        plan = contract_plan()
        before = deepcopy(plan)
        heads = head_bindings(plan)
        heads["numeric_0_3"]["values"][0] = "changed"
        self.assertEqual(plan, before)

    def test_report_preserves_literal_taught_example_without_sealed_rows(self):
        report = audit_summary(contract_plan())
        self.assertEqual(report["example"], {"source": "ADD(1,2)", "direct": "3",
                         "native_output_identity": "school.number.3", "native_output_token_id": 3,
                         "correct_claim": "TRUE", "incorrect_claim": "FALSE"})
        self.assertNotIn("pairs", report)
        self.assertFalse(report["qualification_authorized"])

    def test_native_numeric_answer_uses_exact_model_identity(self):
        self.assertEqual(_native_output("numeric_0_3", "3", {"school.number.3": 137}),
                         {"identity": "school.number.3", "token_id": 137})
        self.assertIsNone(_native_output("evidence", "TRUE", {}))
        with self.assertRaisesRegex(ValueError, "^PARITY_DIRECT_NUMBER_NOT_IN_MODEL_SEMANTIC_ABI$"):
            _native_output("numeric_0_3", "4", {"school.number.4": 138})
