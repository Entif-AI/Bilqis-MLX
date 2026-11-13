"""Candidate admission."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, Settings, decide, paired_outcomes,
    predicted, sampled_protection,
)


class CandidateAdmission3Tests(CausalTeacherExperimentTests):
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

    def test_late_stage_protection_scales_with_probe_and_vetoes_concentrated_loss(self):
        settings = Settings(probe_each=6, mature_max_loss=1,
                            introduction_extra_loss=2)
        fixed = {"status": "MEASURED", "grade": "C",
                 "cohort_sha256": "a" * 64,
                 "before": 50, "after": 53, "total": 66}
        frontier = {"status": "MEASURED", "before_correct": 151,
                    "after_correct": 154, "rows": 186,
                    "regressions": [], "repaired": [],
                    "grades": {"C": {"before": 50, "after": 53,
                                      "total": 66}}}
        acceptable = decide({
            "C.COUNT": {"before": 14, "after": 23, "total": 33},
            "C.NUMBER": {"before": 31, "after": 29, "total": 33},
        }, active_capability="C.COUNT", phase="RECOVERY_1",
            protected={"C.NUMBER"}, settings=settings,
            same_grade_capabilities=("C.COUNT", "C.NUMBER"),
            fixed_grade_replay=fixed, fixed_frontier_replay=frontier,
            protected_frontier_grade="C")
        self.assertEqual(acceptable["protected_tolerances"], {"C.NUMBER": 5})
        self.assertEqual(acceptable["exceeded"], {})
        self.assertEqual(acceptable["decision"], "PROVISIONAL")

        concentrated = decide({
            "C.COUNT": {"before": 14, "after": 23, "total": 33},
            "C.NUMBER": {"before": 33, "after": 27, "total": 33},
        }, active_capability="C.COUNT", phase="RECOVERY_1",
            protected={"C.NUMBER"}, settings=settings,
            same_grade_capabilities=("C.COUNT", "C.NUMBER"),
            fixed_grade_replay=fixed, fixed_frontier_replay=frontier,
            protected_frontier_grade="C")
        self.assertEqual(concentrated["protected_tolerances"], {"C.NUMBER": 5})
        self.assertEqual(concentrated["exceeded"], {"C.NUMBER": 6})
        self.assertEqual(concentrated["reason"], "PROTECTED_CAPABILITY_REGRESSION")
        self.assertEqual(concentrated["decision"], "REJECT")

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
