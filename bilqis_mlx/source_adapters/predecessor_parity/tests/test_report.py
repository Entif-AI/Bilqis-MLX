"""Predecessor-derived curriculum tests, with no model or optimizer writes."""

from copy import deepcopy
from pathlib import Path
import unittest

from bilqis_mlx.pedagogical_parity import (
    audit_summary, build_plan, eligible_stage, head_bindings,
    predecessor_instruction_choice, predecessor_teaching_batch, validate_plan,
)


from bilqis_mlx.source_adapters.predecessor_parity.tests.fixtures import PredecessorFixture, LEGACY


class PredecessorReportTests(PredecessorFixture):
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
