"""Read-only and disposable proof of parent-vs-trial teacher feedback."""
import random
import unittest

import numpy as np

from bilqis_mlx.learning_experiment import (
    Settings, paired_outcomes, decide, contextual_pick, observe_context,
    fork_student, commit_trial, sampled_protection, selection_credit,
)


def rows():
    return [
        {"id": cap + str(i), "capability": cap,
         "gold": "TRUE" if i % 2 else "FALSE"}
        for cap in ("A.EDGE", "B.XOR", "C.ADD") for i in range(6)
    ]


def predicted(rows_, wrong):
    return {row["id"]: ("TRUE" if row["gold"] == "FALSE" else "FALSE")
            if row["id"] in wrong else row["gold"] for row in rows_}


class CausalTeacherExperimentTests(unittest.TestCase):
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

    def test_vulnerable_boolean_anchor_flip_vetoes_positive_c_trial_and_teaches_teacher(self):
        paired = {"C.SUCCESSOR": {"before": 20, "after": 21, "total": 21},
                  "B.XOR": {"before": 6, "after": 6, "total": 6}}
        replay = {"status": "MEASURED", "cohort_sha256": "a" * 64,
                  "rows": 24, "regressions": [{"id": "xor_true_case", "capability": "B.XOR"}],
                  "repaired": 1}
        trial = decide(paired, active_capability="C.SUCCESSOR", phase="MAIN",
                       protected={"B.XOR"}, settings=Settings(),
                       mature_grades=frozenset({"A", "B"}), fragile_replay=replay)
        self.assertEqual(trial["decision"], "REJECT")
        self.assertEqual(trial["reason"], "FRAGILE_COMPOSITION_REPLAY_REGRESSION")
        self.assertEqual(trial["fragile_replay"]["regressions"], replay["regressions"])
        teacher = {"strategies": {"p": {"lr": 0.0001}}}
        observe_context(teacher, capability="C.SUCCESSOR", phase="MAIN",
                        policy_key="p", decision=trial, local_gain=0.03)
        strategy = teacher["causal_experiment"]["contexts"]["C.SUCCESSOR|MAIN|"]["p"]
        self.assertEqual(strategy["unsafe"], 1)
        self.assertEqual(strategy["latest_fragile_replay"]["regressions"], 1)
        replay["regressions"] = []
        safe = decide(paired, active_capability="C.SUCCESSOR", phase="MAIN",
                      protected={"B.XOR"}, settings=Settings(), fragile_replay=replay)
        self.assertEqual(safe["decision"], "PROVISIONAL")

    def setUp(self):
        self.rows = rows()
        self.before = predicted(self.rows, {"C.ADD0", "C.ADD1", "C.ADD2"})

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

    def test_recovery_rejects_small_unproductive_cumulative_regression(self):
        scores = paired_outcomes(self.rows, self.before,
                                 predicted(self.rows, {"B.XOR0", "C.ADD0", "C.ADD1", "C.ADD2"}))
        mature = decide(scores, active_capability="C.ADD", phase="RECOVERY_2",
                        protected={"B.XOR"}, settings=Settings())
        self.assertEqual(mature["worst_protected_loss"], 1)
        self.assertEqual(mature["local_correct_delta"], 0)
        self.assertEqual(mature["decision"], "REJECT")
        self.assertEqual(mature["reason"], "NO_MEASURABLE_TARGET_GAIN")
        developmental = decide(scores, active_capability="C.ADD", phase="MAIN",
                               protected={"B.XOR"}, settings=Settings())
        self.assertEqual(developmental["decision"], "REJECT")
        self.assertEqual(developmental["reason"], "NO_MEASURABLE_TARGET_GAIN")

    def test_no_gain_must_reject_in_every_phase_even_if_older_skills_improve(self):
        # C stays at 3/6; B improves. A global net-positive vote is not
        # evidence that the targeted C capability learned anything.
        scores = {
            "C.ADD": {"before": 3, "after": 3, "total": 6},
            "B.XOR": {"before": 4, "after": 5, "total": 6},
        }
        for phase in ("MAIN", "RECOVERY_1", "RECOVERY_2"):
            with self.subTest(phase=phase):
                outcome = decide(scores, active_capability="C.ADD",
                                 phase=phase, protected={"B.XOR"},
                                 settings=Settings(), mature_grades=frozenset({"B"}))
                self.assertEqual(outcome["decision"], "REJECT")
                self.assertEqual(outcome["reason"], "NO_MEASURABLE_TARGET_GAIN")
                self.assertEqual(outcome["local_correct_delta"], 0)
                self.assertEqual(outcome["active_probe_before"], 3)
                self.assertEqual(outcome["active_probe_after"], 3)
                self.assertEqual(outcome["active_probe_total"], 6)
                self.assertEqual(outcome["protected_net_correct_delta"], 1)

    def test_target_regression_rejected_even_with_positive_other_grade(self):
        outcome = decide({
            "C.ADD": {"before": 4, "after": 3, "total": 6},
            "B.XOR": {"before": 4, "after": 6, "total": 6},
        }, active_capability="C.ADD", phase="MAIN", protected={"B.XOR"},
            settings=Settings(), mature_grades=frozenset({"B"}))
        self.assertEqual(outcome["reason"], "NO_MEASURABLE_TARGET_GAIN")
        self.assertEqual(outcome["local_correct_delta"], -1)
        self.assertEqual(outcome["decision"], "REJECT")

    def test_mature_grades_never_inherit_developmental_loss_budget(self):
        rows = {
            "C.ADD": {"before": 3, "after": 4, "total": 6},
            "B.XOR": {"before": 6, "after": 4, "total": 6},
            "C.SUB": {"before": 6, "after": 4, "total": 6},
        }
        settings = Settings(probe_each=6, mature_max_loss=1,
                            introduction_extra_loss=2)
        result = decide(rows, active_capability="C.ADD", phase="MAIN",
                        protected={"B.XOR", "C.SUB"}, settings=settings,
                        mature_grades=frozenset({"A", "B"}))
        self.assertEqual(result["local_correct_delta"], 1)
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "PROTECTED_CAPABILITY_REGRESSION")
        self.assertEqual(result["exceeded"], {"B.XOR": 2})
        self.assertEqual(result["protected_tolerances"], {"B.XOR": 1, "C.SUB": 3})
        self.assertEqual(result["mature_protected_capabilities"], ["B.XOR"])
        rows["B.XOR"] = {"before": 6, "after": 5, "total": 6}
        passing = decide(rows, active_capability="C.ADD", phase="MAIN",
                         protected={"B.XOR", "C.SUB"}, settings=settings,
                         mature_grades=frozenset({"A", "B"}))
        self.assertEqual(passing["decision"], "PROVISIONAL")

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

    def test_incomplete_or_duplicate_paired_cohort_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "INCOMPLETE"):
            paired_outcomes(self.rows, self.before, {})
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            paired_outcomes(self.rows+self.rows[:1], self.before, self.before)

    def test_bounded_protection_rotates_thousands_of_capabilities(self):
        admitted={f"{grade}.CAP{i:04d}" for grade in "ABCDEFGH"
                  for i in range(500)}
        admitted.add("C.ACTIVE")
        scores={cap: {"correct":1, "total":6} if cap.endswith("0011")
                else {"correct":6, "total":6} for cap in admitted}
        samples=[sampled_protection(admitted,"C.ACTIVE",scores,
                   cap_limit=8,rotation=turn) for turn in range(30)]
        self.assertTrue(all(len(sample)==8 for sample in samples))
        self.assertTrue(all({cap.partition(".")[0] for cap in sample}
                            == set("ABCDEFGH") for sample in samples))
        self.assertGreater(len(set().union(*samples)),8)

    def test_parent_adamw_remains_unchanged_until_trial_committed(self):
        import mlx.core as mx
        import mlx.optimizers as optim
        mx.set_default_device(mx.cpu)
        weights = {"embedding.weight": mx.array(np.arange(12).reshape(3,4).astype(np.float32))}
        parent = optim.AdamW(learning_rate=.00013, bias_correction=True)
        parent.update(weights, {"embedding.weight": mx.zeros_like(weights["embedding.weight"])})
        mx.eval(weights,parent.state)
        parent_weight = np.asarray(weights["embedding.weight"]).copy()
        parent_moment = np.asarray(parent.state["embedding.weight"]["m"]).copy()
        parent_step = int(parent.state["step"].item())
        branch, branch_opt = fork_student(mx, weights, parent)
        branch_opt.update(branch, {"embedding.weight": mx.ones_like(branch["embedding.weight"])})
        mx.eval(branch,branch_opt.state)
        self.assertEqual(int(parent.state["step"].item()), parent_step)
        np.testing.assert_array_equal(np.asarray(weights["embedding.weight"]), parent_weight)
        np.testing.assert_array_equal(np.asarray(parent.state["embedding.weight"]["m"]), parent_moment)
        self.assertNotEqual(int(branch_opt.state["step"].item()), parent_step)
        commit_trial(weights, parent, branch, branch_opt)
        self.assertEqual(int(parent.state["step"].item()), parent_step+1)
        self.assertFalse(np.array_equal(np.asarray(weights["embedding.weight"]), parent_weight))


if __name__ == "__main__":
    unittest.main()
