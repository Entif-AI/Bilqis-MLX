"""Grade A gold can only be scored against the exact sealed exam inventory."""
from pathlib import Path
import unittest

from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.grade_a_evaluator import score_predictions
from bilqis_mlx.grade_a_manifest import build_manifest
from bilqis_mlx.grade_a_probe import candidate_course

ROOT = Path(__file__).resolve().parents[3] / "vendor" / "legacy-v16"
SOURCE = ROOT / "runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt"


@unittest.skipUnless(SOURCE.is_file(), "Original source checkpoint not mounted")
class GradeAEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate = build_manifest(ROOT, SOURCE)
        cls.course = candidate_course()
        cls.student = Checkpoint("e"*64, "disposable-student.pt", 116800, True)
        cls.answer_key = {row["id"]: row["gold"]
                          for row in cls.candidate["examination_rows"]}

    def grade(self, predictions):
        return score_predictions(self.candidate, self.course, self.student,
                                 predictions, legacy_root=ROOT,
                                 source_checkpoint=SOURCE)

    def test_72_answers_all_correct_yields_six_full_12_of_12_scores(self):
        result = self.grade(self.answer_key)
        self.assertEqual(len(result.scores), 6)
        self.assertEqual([(score.correct, score.total)
                          for score in result.scores.values()], [(12,12)]*6)
        self.assertEqual(result.rubric_digest,
                         self.candidate["exam_rubric_sha256"])
        self.assertEqual(result.checkpoint_sha256, self.student.sha256)
        self.assertEqual(result.optimizer_step, self.student.optimizer_step)

    def test_one_wrong_answer_changes_the_actual_held_out_score(self):
        altered = dict(self.answer_key)
        one_id = self.candidate["examination_rows"][0]["id"]
        altered[one_id] = ("FALSE" if altered[one_id] == "TRUE" else "TRUE")
        result = self.grade(altered)
        self.assertEqual(result.scores["A.IDENTITY"].correct, 11)
        self.assertEqual(result.scores["A.IDENTITY"].total, 12)
        self.assertEqual(result.scores["A.MEMBER"].correct, 12)

    def test_missing_extra_or_untyped_answers_refuse_assessment(self):
        one = next(iter(self.answer_key))
        with self.assertRaisesRegex(ValueError, "INCOMPLETE"):
            self.grade({k: v for k, v in self.answer_key.items() if k != one})
        with self.assertRaisesRegex(ValueError, "INCOMPLETE"):
            self.grade({**self.answer_key, "invented": "TRUE"})
        with self.assertRaisesRegex(ValueError, "WRONG_ANSWER_TYPE"):
            self.grade({**self.answer_key, one: "UNKNOWN"})


if __name__ == "__main__":
    unittest.main()
