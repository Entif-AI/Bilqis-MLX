import json
from pathlib import Path
import unittest

from bilqis_mlx.factory.assessment import qualification_complete
from bilqis_mlx.factory.model import AssessmentClass, LearningEvidence


FIXTURE = Path(__file__).parent / "fixtures/historical_b_false_mastery.json"


class HistoricalGeneralizationRegressionTests(unittest.TestCase):
    def test_historical_b_false_graduate_is_rejected(self):
        evidence = json.loads(FIXTURE.read_text())
        checkpoint = evidence["checkpoint"]
        promotion = evidence["promotion"]
        fresh = evidence["fresh_generalization"]
        self.assertEqual((promotion["b_correct"], promotion["b_total"]), (72, 72))
        self.assertLess(fresh["b_correct"], fresh["b_total"])
        classroom = LearningEvidence(
            AssessmentClass.PROMOTION,
            promotion["cohort_sha256"], checkpoint["sha256"],
            checkpoint["optimizer_step"], True)
        generalization = LearningEvidence(
            AssessmentClass.GENERALIZATION,
            fresh["cohort_sha256"], checkpoint["sha256"],
            checkpoint["optimizer_step"], False)
        self.assertFalse(qualification_complete(classroom, generalization))

    def test_fresh_generalization_cannot_reuse_promotion_cohort(self):
        evidence = json.loads(FIXTURE.read_text())
        checkpoint = evidence["checkpoint"]
        digest = evidence["promotion"]["cohort_sha256"]
        classroom = LearningEvidence(
            AssessmentClass.PROMOTION, digest, checkpoint["sha256"],
            checkpoint["optimizer_step"], True)
        copied = LearningEvidence(
            AssessmentClass.GENERALIZATION, digest, checkpoint["sha256"],
            checkpoint["optimizer_step"], True)
        with self.assertRaisesRegex(ValueError, "DISTINCT_COHORT"):
            qualification_complete(classroom, copied)


if __name__ == "__main__":
    unittest.main()
