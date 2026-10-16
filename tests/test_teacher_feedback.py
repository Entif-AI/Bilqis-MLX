"""Teacher feedback receipts are source-neutral and never optimize a student."""
from __future__ import annotations

import unittest

from bilqis_mlx.diagnostics import DiagnosticStatus, LearningSignal
from bilqis_mlx.teacher_feedback import (
    FairMissRequest,
    OutcomeAttribution,
    TeacherDecisionInput,
    TeachingOpportunity,
    active_warning_signals,
    reconcile_unresolved_misses,
    select_fair_miss_window,
    summarize_teacher_decision,
    summarize_teacher_outcomes,
)


class TeacherFeedbackTests(unittest.TestCase):
    def test_unresolved_misses_survive_new_cohorts_until_the_same_item_is_correct(self):
        prior = [
            {"id":"old-only", "capability":"B.NOT", "gold":"TRUE"},
            {"id":"retested", "capability":"B.NOT", "gold":"FALSE"},
        ]
        rows = [
            {"id":"retested", "capability":"B.NOT", "gold":"FALSE"},
            {"id":"new-miss", "capability":"B.NOT", "gold":"TRUE"},
        ]
        result = reconcile_unresolved_misses(
            prior, rows, {"retested":"FALSE", "new-miss":"FALSE"})
        self.assertEqual([row["id"] for row in result], ["new-miss", "old-only"])

    def test_fair_miss_selection_covers_backlog_without_a_fixed_batch_ratio(self):
        misses = [{"id":f"miss-{index:02d}", "capability":"B.NOT",
                   "gold":"TRUE" if index % 2 else "FALSE"}
                  for index in range(22)]
        exposures = {row["id"]: 0 for row in misses}
        selected_this_visit = set()
        for remaining_steps in range(6, 0, -1):
            window = select_fair_miss_window(
                misses, FairMissRequest(
                    exposures=exposures,
                    selected_this_visit=frozenset(selected_this_visit),
                    remaining_steps=remaining_steps, batch_size=8,
                    gold_capacity={"TRUE":4, "FALSE":4}))
            self.assertLessEqual(len(window), 8)
            self.assertLessEqual(sum(row["gold"] == "TRUE" for row in window), 4)
            self.assertLessEqual(sum(row["gold"] == "FALSE" for row in window), 4)
            for row in window:
                exposures[row["id"]] += 1
                selected_this_visit.add(row["id"])
        self.assertEqual(selected_this_visit, {row["id"] for row in misses})
        self.assertEqual(set(exposures.values()), {1})
        large_backlog = misses + [
            {"id":f"more-{index:02d}", "capability":"B.NOT",
             "gold":"TRUE" if index % 2 else "FALSE"}
            for index in range(18)]
        self.assertEqual(len(select_fair_miss_window(
            large_backlog, FairMissRequest(
                exposures={}, selected_this_visit=frozenset(),
                remaining_steps=2, batch_size=8,
                gold_capacity={"TRUE":4, "FALSE":4}))), 8)
        all_true = [{"id":f"true-{index:02d}", "capability":"B.NOT", "gold":"TRUE"}
                    for index in range(22)]
        seen_true = set()
        for remaining_steps in range(6, 0, -1):
            window = select_fair_miss_window(
                all_true, FairMissRequest(
                    exposures={}, selected_this_visit=frozenset(seen_true),
                    remaining_steps=remaining_steps, batch_size=8,
                    gold_capacity={"TRUE":4, "FALSE":4}))
            self.assertLessEqual(len(window), 4)
            self.assertTrue(all(row["gold"] == "TRUE" for row in window))
            seen_true.update(row["id"] for row in window)
        self.assertEqual(seen_true, {row["id"] for row in all_true})

    def test_only_observed_diagnostics_enter_teacher_warning_context(self):
        exam = {"learning_diagnostics":{"findings":[
            {"capability":"B.NOT", "signal":LearningSignal.REPETITIVE_ANSWERS,
             "target":"CAPABILITY", "status":DiagnosticStatus.OBSERVED_IN_COHORT},
            {"capability":"B", "signal":LearningSignal.CHANCE_LEVEL_OR_LAGGING,
             "target":"GRADE", "status":DiagnosticStatus.OBSERVED_IN_COHORT},
            {"capability":"A", "signal":LearningSignal.LACK_OF_DURABLE_GAIN,
             "target":"GRADE", "status":DiagnosticStatus.OBSERVED_LONGITUDINALLY},
            {"capability":"B.NOT", "signal":LearningSignal.LACK_OF_DURABLE_GAIN,
             "target":"CAPABILITY", "status":DiagnosticStatus.NOT_MEASURED},
        ]}}
        methodology = {"findings":[
            {"capability":"B.NOT", "signal":LearningSignal.DISCONNECTED_PREREQUISITES,
             "status":DiagnosticStatus.OBSERVED_IN_INSTRUCTION},
            {"capability":"B.NOT", "signal":LearningSignal.EXCESSIVE_INTRODUCTORY_COMPLEXITY,
             "status":DiagnosticStatus.NOT_OBSERVED},
        ]}
        self.assertEqual(active_warning_signals(exam, methodology, "B.NOT"), (
            LearningSignal.REPETITIVE_ANSWERS,
            LearningSignal.CHANCE_LEVEL_OR_LAGGING,
            LearningSignal.DISCONNECTED_PREREQUISITES,
        ))

    def test_decision_records_actual_strategy_options_and_delivered_actions(self):
        decision = summarize_teacher_decision(TeacherDecisionInput(
            capability="B.NOT", policy_key="policy-1",
            warnings=(LearningSignal.REPETITIVE_ANSWERS,
                      LearningSignal.EXCESSIVE_INTRODUCTORY_COMPLEXITY),
            unresolved_miss_count=3, champion_candidate_count=5,
            prerequisite_capabilities=("A.IDENTITY","A.PARENT","A.LINK"),
            methodology={"constituent_capabilities_delivered":["A.IDENTITY"],
                         "simplest_delivered_first_batch":[1, 5]},
            delivered_examples=32, replayed_misses=3,
            resolved_exam_misses=2, champion_prioritized=7, seed=44,
        ))
        self.assertEqual(decision["capability"], "B.NOT")
        self.assertEqual(decision["policy_key"], "policy-1")
        self.assertEqual(decision["policy_selection"], {
            "origin":"INHERITED_LEGACY_UCB",
            "diagnostic_context_consumed":False,
        })
        self.assertEqual(set(decision["opportunities"]), {
            TeachingOpportunity.EXAM_MISTAKE_REPLAY,
            TeachingOpportunity.PREREQUISITE_CONNECTION,
            TeachingOpportunity.SIMPLER_INTRODUCTION,
            TeachingOpportunity.CHAMPION_PRIORITY,
        })
        self.assertEqual(decision["selected"]["exam_mistake_replay"], 3)
        self.assertEqual(decision["selected"]["exam_mistakes_resolved"], 2)
        self.assertEqual(decision["selected"]["champion_priority"], 7)
        self.assertEqual(decision["selected"]["prerequisite_connections"],
                         ["A.IDENTITY"])
        self.assertEqual(decision["selected"]["simplest_delivered_first_batch"], [1, 5])
        self.assertEqual(len(decision["decision_id"]), 64)

    def test_same_fixed_exam_gives_exact_delayed_outcome_and_ambiguity_control(self):
        previous = {"cohort_sha256":"c"*64, "optimizer_step":100,
                    "scores":{"B.NOT":{"correct":3,"total":12}}}
        current = {"cohort_sha256":"c"*64, "optimizer_step":120,
                   "scores":{"B.NOT":{"correct":7,"total":12}}}
        decision = {"decision_id":"d"*64, "capability":"B.NOT",
                    "policy_key":"policy-1"}
        pending = [{"capability":"B.NOT", "teacher_decision":decision}]
        outcome = summarize_teacher_outcomes(previous, current, pending)[0]
        self.assertEqual(outcome["attribution"],
                         OutcomeAttribution.MEASURED_FIXED_EXAM_UNIQUE_ACTION)
        self.assertEqual((outcome["before_correct"], outcome["after_correct"],
                          outcome["total"], outcome["delta_correct"]), (3,7,12,4))
        self.assertEqual(outcome["decision_ids"], ["d"*64])

        ambiguous = summarize_teacher_outcomes(previous, current, pending * 2)[0]
        self.assertEqual(ambiguous["attribution"],
                         OutcomeAttribution.NOT_MEASURED_MULTIPLE_ACTIONS)
        self.assertIsNone(ambiguous["delta_correct"])

        changed = summarize_teacher_outcomes(
            previous, {**current, "cohort_sha256":"e"*64}, pending)[0]
        self.assertEqual(changed["attribution"],
                         OutcomeAttribution.NOT_MEASURED_CHANGED_EXAM)

    def test_other_capability_optimizer_visits_prevent_unique_causal_attribution(self):
        """XOR forgetting after teaching NOT is not uniquely attributable to XOR."""
        previous = {"cohort_sha256": "c"*64, "optimizer_step": 100,
                    "scores": {"B.XOR": {"correct": 12, "total": 12},
                               "B.NOT": {"correct": 12, "total": 12}}}
        current = {"cohort_sha256": "c"*64, "optimizer_step": 132,
                   "scores": {"B.XOR": {"correct": 8, "total": 12},
                              "B.NOT": {"correct": 9, "total": 12}}}
        pending = [
            {"teacher_decision": {"capability": "B.XOR", "policy_key": "minerva",
                                  "decision_id": "x"*64}},
            {"teacher_decision": {"capability": "B.NOT", "policy_key": "minerva",
                                  "decision_id": "n"*64}},
        ]
        outcomes = summarize_teacher_outcomes(previous, current, pending)
        self.assertEqual({row["capability"] for row in outcomes}, {"B.XOR", "B.NOT"})
        self.assertEqual({row["attribution"] for row in outcomes},
                         {OutcomeAttribution.NOT_MEASURED_MULTIPLE_ACTIONS})
        self.assertTrue(all(row["delta_correct"] is None for row in outcomes))


if __name__ == "__main__":
    unittest.main()
