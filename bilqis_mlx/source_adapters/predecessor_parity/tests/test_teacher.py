"""Predecessor-derived curriculum tests, with no model or optimizer writes."""

from copy import deepcopy
from pathlib import Path
import unittest

from bilqis_mlx.pedagogical_parity import (
    audit_summary, build_plan, eligible_stage, head_bindings,
    predecessor_instruction_choice, predecessor_teaching_batch, validate_plan,
)


from bilqis_mlx.source_adapters.predecessor_parity.tests.fixtures import PredecessorFixture, LEGACY


class PredecessorTeacherTests(PredecessorFixture):
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
