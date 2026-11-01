"""Feedback."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, Settings, _effective_policy_key, contextual_pick,
    decide, observe_context, paired_outcomes, predicted,
    random, selection_credit,
)


class Feedback1Tests(CausalTeacherExperimentTests):
    def test_primary_bandit_receives_negative_rejection_credit_instead_of_zero(self):
        rejected = {"decision": "REJECT"}
        credit = {"teacher_context_reward": -0.05}
        self.assertEqual(selection_credit(0.0, rejected, credit), -0.05)
        accepted = {"decision": "PROVISIONAL"}
        self.assertEqual(selection_credit(0.0, accepted,
                                          {"teacher_context_reward": 1/21}), 1/21)
        self.assertEqual(selection_credit(0.125, None, None), 0.125)
        with self.assertRaisesRegex(ValueError, "INVALID_SELECTION_CREDIT"):
            selection_credit(0.0, rejected, {"teacher_context_reward": 0.0})

    def test_one_parent_two_outcomes_and_phase_specific_gate(self):
        after = predicted(self.rows, {
            "B.XOR0", "B.XOR1", "B.XOR2", "C.ADD0"})
        scores = paired_outcomes(self.rows, self.before, after)
        self.assertEqual(scores["C.ADD"]["after"]-scores["C.ADD"]["before"], 2)
        self.assertEqual(scores["B.XOR"]["before"]-scores["B.XOR"]["after"], 3)
        settings = Settings(probe_each=6, mature_max_loss=2, introduction_extra_loss=2)
        provisional = decide(scores, active_capability="C.ADD", phase="MAIN",
                             protected={"A.EDGE", "B.XOR"}, settings=settings)
        mature_main = decide(scores, active_capability="C.ADD", phase="MAIN",
                             protected={"A.EDGE", "B.XOR"}, settings=settings,
                             mature_grades=frozenset({"A", "B"}))
        rejected = decide(scores, active_capability="C.ADD", phase="RECOVERY_1",
                          protected={"A.EDGE", "B.XOR"}, settings=settings)
        self.assertEqual(provisional["decision"], "PROVISIONAL")
        self.assertEqual(mature_main["decision"], "REJECT")
        self.assertEqual(mature_main["exceeded"], {"B.XOR": 3})
        self.assertEqual(mature_main["protected_tolerances"]["B.XOR"], 2)
        self.assertEqual(rejected["decision"], "REJECT")
        self.assertEqual(rejected["exceeded"], {"B.XOR": 3})
        self.assertFalse(rejected["exact_complete_exam_qualification"])
        self.assertEqual(rejected["paired_scores_sha256"], provisional["paired_scores_sha256"])
        with self.assertRaisesRegex(ValueError, "NOT_MEASURED"):
            decide(scores, active_capability="C.ADD", phase="RECOVERY_1",
                   protected={"A.MAPS"}, settings=settings)

    def test_teacher_context_learns_negative_evidence_without_mutating_prior(self):
        from copy import deepcopy
        settings = Settings()
        scores = paired_outcomes(self.rows, self.before,
                                 predicted(self.rows, {"B.XOR0", "B.XOR1", "B.XOR2"}))
        evidence = decide(scores, active_capability="C.ADD", phase="RECOVERY_2",
                          protected={"B.XOR"}, settings=settings)
        teacher = {"strategies": {"positive": {"lr": .0001}, "negative": {"lr": .0002}},
                   "global_stats": {"positive": {"trials": 12, "reward_sum": 3.},
                                    "negative": {"trials": 8, "reward_sum": 5.}}}
        historic = deepcopy(teacher["global_stats"])
        for _ in range(2):
            result = observe_context(teacher, capability="C.ADD",
                                     phase="RECOVERY_2", policy_key="negative",
                                     decision=evidence, local_gain=.1)
        self.assertLess(result["teacher_context_reward"], 0)
        self.assertEqual(teacher["global_stats"], historic)
        self.assertEqual(len(teacher["causal_experiment"]["negative_archetypes"]), 1)

        class Legacy:
            @staticmethod
            def pick(_t, _grade, _rng):
                return "negative", _t["strategies"]["negative"]

        accepted = decide(paired_outcomes(self.rows, self.before,
                            predicted(self.rows, {"C.ADD0"})),
                          active_capability="C.ADD", phase="RECOVERY_2",
                          protected={"B.XOR"}, settings=settings)
        for _ in range(3):
            observe_context(teacher, capability="C.ADD", phase="RECOVERY_2",
                            policy_key="positive", decision=accepted, local_gain=.4)
        pick, _ = contextual_pick(Legacy, teacher, "C.ADD", "RECOVERY_2", random.Random(2))
        self.assertEqual(pick, "positive")

    def test_provisional_protected_loss_becomes_typed_negative_evidence(self):
        scores = paired_outcomes(self.rows, self.before,
                                 predicted(self.rows, {"B.XOR0", "C.ADD0"}))
        decision = decide(scores, active_capability="C.ADD", phase="RECOVERY_1",
                          protected={"B.XOR"}, settings=Settings())
        self.assertEqual(decision["decision"], "PROVISIONAL")
        self.assertEqual(decision["worst_protected_loss"], 1)
        teacher = {"strategies": {"p": {"lr": .0001}}}
        observed = observe_context(teacher, capability="C.ADD", phase="RECOVERY_1",
                                   policy_key="p", decision=decision, local_gain=0.)
        self.assertLess(observed["teacher_context_reward"], 0.)
        self.assertEqual(teacher["causal_experiment"]["negative_archetypes"][0]["outcome"],
                         "ACCEPTED_WITH_MEASURED_PROTECTED_LOSS")
        self.assertEqual(teacher["causal_experiment"]["contexts"]["C.ADD|RECOVERY_1|"]["p"]["unsafe"], 0)

    def test_teacher_learns_rejected_nonprogress_without_legacy_reward_rewrite(self):
        from copy import deepcopy
        decision = decide({
            "C.ADD": {"before": 3, "after": 3, "total": 6},
            "B.XOR": {"before": 6, "after": 6, "total": 6},
        }, active_capability="C.ADD", phase="MAIN", protected={"B.XOR"},
            settings=Settings(), mature_grades=frozenset({"B"}))
        teacher = {"strategies": {"p": {"lr": .0001}},
                   "global_stats": {"p": {"trials": 9, "reward_sum": 3.}}}
        historic = deepcopy(teacher["global_stats"])
        outcome = observe_context(teacher, capability="C.ADD", phase="MAIN",
                                  policy_key="p", decision=decision,
                                  local_gain=.75)
        self.assertLess(outcome["teacher_context_reward"], 0.)
        self.assertEqual(teacher["global_stats"], historic)
        self.assertEqual(teacher["causal_experiment"]["events"], 1)
        self.assertEqual(teacher["causal_experiment"]["contexts"]["C.ADD|MAIN|"]["p"]["unsafe"], 1)
        self.assertEqual(teacher["causal_experiment"]["negative_archetypes"][0]["outcome"],
                         "REJECTED_UPDATE")

    def test_realized_delivery_variants_keep_separate_outcome_evidence(self):
        import bilqis_mlx.learning.learning_experiment as experiment
        teacher = {
            "strategies": {
                "variable": {"lr": .0001, "old": 16, "depth": 3,
                             "contrast": 1.0},
            },
            "global_stats": {}, "grade_stats": {}, "events": 0,
        }
        retained = decide({
            "C.ADD": {"before": 3, "after": 5, "total": 6},
        }, active_capability="C.ADD", phase="MAIN", protected=set(),
            settings=Settings())
        rejected = decide({
            "C.ADD": {"before": 3, "after": 3, "total": 6},
        }, active_capability="C.ADD", phase="MAIN", protected=set(),
            settings=Settings())
        common = dict(candidate_steps=16, batch_size=32,
                      guidance_applied_steps=0, enrichment_examples=0)
        first_action = experiment.realized_teacher_action(
            teacher["strategies"]["variable"],
            policy_controls=({"effective_old_grade_examples": 12},), **common)
        second_action = experiment.realized_teacher_action(
            teacher["strategies"]["variable"],
            policy_controls=({"effective_old_grade_examples": 9},), **common)
        self.assertNotEqual(first_action["key"], second_action["key"])

        first = observe_context(
            teacher, capability="C.ADD", phase="MAIN", policy_key="variable",
            decision=retained, local_gain=.4, curriculum_scope="scope",
            realized_action=first_action)
        second = observe_context(
            teacher, capability="C.ADD", phase="MAIN", policy_key="variable",
            decision=rejected, local_gain=0., curriculum_scope="scope",
            realized_action=second_action)
        record = teacher["causal_experiment"]["contexts"]["C.ADD|MAIN|scope"][
            "variable"]

        self.assertEqual(record["trials"], 2)
        self.assertEqual(record["retained"], 1)
        self.assertEqual(record["realized_actions"][first_action["key"]]["retained"], 1)
        self.assertEqual(record["realized_actions"][second_action["key"]]["unsafe"], 1)
        self.assertEqual(first["realized_action_key"], first_action["key"])
        self.assertEqual(second["realized_action_key"], second_action["key"])
        ecology = teacher["causal_experiment"]["realized_action_ecology"]
        self.assertEqual(ecology[first_action["key"]]["trials"], 1)
        self.assertEqual(ecology[first_action["key"]]["retained"], 1)
        self.assertEqual(ecology[second_action["key"]]["trials"], 1)
        self.assertEqual(ecology[second_action["key"]]["retained"], 0)
        self.assertEqual(
            ecology[first_action["key"]]["effective_policy_keys"],
            [_effective_policy_key(teacher["strategies"]["variable"])])
