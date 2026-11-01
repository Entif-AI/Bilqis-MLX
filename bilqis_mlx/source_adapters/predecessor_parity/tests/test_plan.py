"""Predecessor-derived curriculum tests, with no model or optimizer writes."""

from copy import deepcopy
from pathlib import Path
import unittest

from bilqis_mlx.pedagogical_parity import (
    audit_summary, build_plan, eligible_stage, head_bindings,
    predecessor_instruction_choice, predecessor_teaching_batch, validate_plan,
)


from bilqis_mlx.source_adapters.predecessor_parity.tests.fixtures import PredecessorFixture, LEGACY


class PredecessorPlanTests(PredecessorFixture):
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
