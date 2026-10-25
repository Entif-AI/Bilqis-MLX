"""Teacher feedback receipts are source-neutral and never optimize a student."""
from __future__ import annotations

import unittest

from bilqis_mlx.diagnostics import DiagnosticStatus, LearningSignal
from bilqis_mlx.learning.teacher_feedback import (
    OutcomeAttribution,
    TeacherDecisionInput,
    TeachingOpportunity,
    WeaknessTargetRequest,
    active_warning_signals,
    reconcile_unresolved_misses,
    select_weakness_targets,
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

    def test_unresolved_misses_dedupe_same_semantics_across_cohort_ids(self):
        semantic = {
            "capability": "C.NUMBER", "gold": "3",
            "source_id": "number-three",
            "record": {"task": "number", "symbols": ["NUMBER", "3"]},
            "tokens": [1, 3, 9],
        }
        prior = [
            {"id": "old-a", "integer_max": 3, **semantic},
            {"id": "old-b", "integer_max": 10, **semantic},
            {"id": "other", "capability": "C.NUMBER", "gold": "2",
             "source_id": "number-two",
             "record": {"task": "number", "symbols": ["NUMBER", "2"]},
             "tokens": [1, 2, 9]},
        ]
        current = [{"id": "new-c", "integer_max": 3, **semantic}]

        still_wrong = reconcile_unresolved_misses(
            prior, current, {"new-c": "2"})
        self.assertEqual([row["id"] for row in still_wrong],
                         ["old-a", "other"])

        now_correct = reconcile_unresolved_misses(
            still_wrong, current, {"new-c": "3"})
        self.assertEqual([row["id"] for row in now_correct], ["other"])

    def test_boolean_miss_reconciles_across_fresh_worlds_by_source_structure(self):
        def row(identity, *, universe=3, kinds=("PARENT", "EQ")):
            def operand(kind, left, right):
                return ({
                    "kind": "compare", "operator": "EQ",
                    "args": [{"kind": "entity", "name": left},
                             {"kind": "entity", "name": right}],
                } if kind == "EQ" else {
                    "kind": "relation", "name": kind,
                    "args": [{"kind": "entity", "name": left},
                             {"kind": "entity", "name": right}],
                })
            return {
                "id": identity, "source_id": identity,
                "capability": "B.AND", "answer_kind": "binary",
                "gold": "FALSE", "operand_truths": [False, True],
                "universe_size": universe, "tokens": [1, 2, 3],
                "record": {"query": {
                    "kind": "apply", "operator": "AND",
                    "args": [operand(kinds[0], "A", "B"),
                             operand(kinds[1], "C", "A")]},
                    "world": {"entities": ["A", "B", "C"]}},
            }

        prior = [row("old-world")]
        equivalent = row("new-world")
        distinct = row("different-shape", kinds=("LINK", "EQ"))
        result = reconcile_unresolved_misses(
            prior, [equivalent, distinct],
            {"new-world": "FALSE", "different-shape": "TRUE"})

        self.assertEqual([item["id"] for item in result], ["different-shape"])

    def test_inverse_boolean_structure_uses_declared_answer_mode(self):
        from bilqis_mlx.boolean_identification import ANSWER_KIND
        from bilqis_mlx.boolean_identification_oracle import TASK
        from bilqis_mlx.learning.teacher_feedback import _source_structural_miss_identity
        row = {
            "capability": "Z.INVERSE", "answer_kind": ANSWER_KIND, "gold": "AND",
            "root": "cogal.operator.AND", "operator_options": ["AND", "OR"],
            "observation_count": 1,
            "record": {"task": TASK, "observations": [{"operands": [
                {"kind": "literal", "value": True},
                {"kind": "literal", "value": False}]}]},
        }
        shape = _source_structural_miss_identity(row)
        self.assertIsNotNone(shape)
        self.assertEqual(shape["root"], row["root"])
        self.assertEqual(shape["operator_options"], ("AND", "OR"))
        self.assertEqual(shape["observation_count"], 1)

    def test_numeric_miss_reconciles_across_permuted_source_construction(self):
        def count_row(identity, members):
            symbols = [
                "school.syntax.math", "school.op.EQ", "school.op.COUNT",
                "school.syntax.number_set",
                *(f"school.number.{value}" for value in members),
                "syntax.end", "school.number.0", "syntax.end",
            ]
            return {
                "id": identity, "source_id": identity,
                "capability": "C.COUNT", "answer_kind": "binary",
                "gold": "FALSE", "integer_max": 4,
                "lesson_id": "LESSON-058",
                "generator": "bilqis.finite-numeric-constructions/v1",
                "oracle": "bilqis.independent-finite-numeric/v1",
                "record": {"task": "bilqis.finite-number-prefix/v1",
                           "symbols": symbols},
                "tokens": list(range(len(symbols))),
                "witness": {"ordinal_members": list(members)},
            }

        prior = [count_row("old-count", [0, 1, 2, 3])]
        equivalent = count_row("new-count", [3, 1, 0, 2])
        result = reconcile_unresolved_misses(
            prior, [equivalent], {"new-count": "FALSE"})

        self.assertEqual(result, [])

    def test_weakness_target_selection_rotates_least_exposed_semantics(self):
        misses = [{"id":f"miss-{index:02d}", "capability":"B.NOT",
                   "gold":"TRUE" if index % 2 else "FALSE"}
                  for index in range(22)]
        exposures = {row["id"]: 0 for row in misses}
        seen = set()
        for _ in range(6):
            window = select_weakness_targets(
                misses, WeaknessTargetRequest(
                    exposures=exposures, capacity=4))
            self.assertEqual(len(window), 4)
            for row in window:
                exposures[row["id"]] += 1
                seen.add(row["id"])
        self.assertEqual(seen, {row["id"] for row in misses})
        self.assertLessEqual(max(exposures.values()) - min(exposures.values()), 1)

    def test_single_weak_semantic_remains_eligible_every_optimizer_step(self):
        miss = {"id": "number-three", "capability": "C.NUMBER", "gold": "3"}
        exposures = {miss["id"]: 0}

        for _ in range(4):
            window = select_weakness_targets(
                [miss], WeaknessTargetRequest(
                    exposures=exposures, capacity=1))
            self.assertEqual([row["id"] for row in window], [miss["id"]])
            exposures[miss["id"]] += 1

        self.assertEqual(exposures[miss["id"]], 4)

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

    def test_decision_records_diagnostic_conditioning_when_selector_used_it(self):
        decision = summarize_teacher_decision(TeacherDecisionInput(
            capability="C.SUB", policy_key="policy-2", warnings=(),
            unresolved_miss_count=2, champion_candidate_count=1,
            prerequisite_capabilities=(), methodology={},
            delivered_examples=16, replayed_misses=1,
            resolved_exam_misses=0, champion_prioritized=1, seed=45,
            diagnostic_context_consumed=True,
            diagnostic_context_key="abc123",
        ))
        self.assertEqual(decision["policy_selection"], {
            "origin": "INHERITED_LEGACY_UCB",
            "diagnostic_context_consumed": True,
            "diagnostic_context_key": "abc123",
        })
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
