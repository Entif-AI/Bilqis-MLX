"""Generated examination is a scored cohort, never a secret inventory."""
import unittest

from bilqis_mlx.generated_assessment import (
    make_cohort, score, compare_on_same_cohort)


class GeneratedAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{"id":"i1","source_id":"expression-1",
                      "capability":"A.NUM","gold":"3"},
                     {"id":"i2","source_id":"expression-1",
                      "capability":"A.TRUTH","gold":"TRUE"},
                     {"id":"i3","source_id":"expression-2",
                      "capability":"A.NUM","gold":"2"}]
        self.cohort = make_cohort(self.rows, generator_version="typed/v2",
                                  seed=23, rubric_version="A/generated/v1")
        self.checkpoint = {"sha256":"whole-student", "optimizer_step":77,
                           "model_and_native_adamw":True}

    def test_missing_prediction_or_partial_checkpoint_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"INCOMPLETE_PREDICTIONS"):
            score(self.cohort,{"i1":"3"},self.checkpoint)
        with self.assertRaisesRegex(ValueError,"COMPLETE_CHECKPOINT_REQUIRED"):
            score(self.cohort,{r["id"]:r["gold"] for r in self.rows},
                  {**self.checkpoint,"model_and_native_adamw":False})

    def test_teacher_can_reuse_every_missed_item_after_scoring(self):
        measured=score(self.cohort,{"i1":"0","i2":"TRUE","i3":"0"},
                       self.checkpoint)
        self.assertEqual([m["id"] for m in measured["misses_for_teacher"]],
                         ["i1","i3"])
        self.assertEqual([m["gold"] for m in measured["misses_for_teacher"]],
                         ["3","2"])
        self.assertFalse(measured["perfect_on_sample"])

    def test_cannot_compare_scores_from_different_seeds_or_sampled_questions(self):
        before=score(self.cohort,{"i1":"0","i2":"TRUE","i3":"0"},
                     self.checkpoint)
        cohort2=make_cohort(self.rows, generator_version="typed/v2",seed=24,
                            rubric_version="A/generated/v1")
        after=score(cohort2,{r["id"]:r["gold"] for r in self.rows},
                    self.checkpoint)
        with self.assertRaisesRegex(ValueError,"COHORT_NOT_COMPARABLE"):
            compare_on_same_cohort(after,before)

    def test_challenger_competes_against_incumbent_on_one_cohort(self):
        old=score(self.cohort,{"i1":"0","i2":"TRUE","i3":"0"},
                  self.checkpoint)
        new=score(self.cohort,{r["id"]:r["gold"] for r in self.rows},
                  {**self.checkpoint,"sha256":"new-full-student"})
        self.assertEqual(compare_on_same_cohort(new,old),
                         ("A.NUM",))
        self.assertTrue(new["perfect_on_sample"])


if __name__ == "__main__":
    unittest.main()
