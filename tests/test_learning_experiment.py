"""Read-only and disposable proof of parent-vs-trial teacher feedback."""
import random
import unittest

import numpy as np

from bilqis_mlx.learning_experiment import (
    Settings, paired_outcomes, decide, contextual_pick, observe_context,
    fork_student, commit_trial, sampled_protection,
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
        rejected = decide(scores, active_capability="C.ADD", phase="RECOVERY_1",
                          protected={"A.EDGE", "B.XOR"}, settings=settings)
        self.assertEqual(provisional["decision"], "PROVISIONAL")
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
        self.assertEqual(mature["reason"], "UNPRODUCTIVE_RECOVERY_INTERFERENCE")
        developmental = decide(scores, active_capability="C.ADD", phase="MAIN",
                               protected={"B.XOR"}, settings=Settings())
        self.assertEqual(developmental["decision"], "PROVISIONAL")

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
