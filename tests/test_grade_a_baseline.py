"""Historic whole-model prediction evidence against fixed Grade A exam questions."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from bilqis_mlx.grade_a_baseline import _fixed_batch, evaluate_parent

ROOT = Path(__file__).resolve().parents[2] / "bilqis-triplets-v16"
CHECKPOINT = ROOT / "runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt"
MANIFEST = Path(__file__).resolve().parents[1] / "docs/GRADE_A_CANDIDATE_MANIFEST_V2.json"


class BatchTests(unittest.TestCase):
    def test_padding_does_not_shift_record_token_boundaries(self):
        ids, lengths = _fixed_batch([
            {"tokens": [7, 9, 4]}, {"tokens": [8, 10]}])
        self.assertEqual(ids.tolist(), [[7, 9, 4], [8, 10, 0]])
        self.assertEqual(lengths.tolist(), [3, 2])
        with self.assertRaisesRegex(ValueError, "EMPTY_BATCH"):
            _fixed_batch([])


@unittest.skipUnless(CHECKPOINT.is_file() and MANIFEST.is_file(),
                     "Original whole-student / manifest not mounted")
class WholeStudentBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_real_source_student_is_scored_across_all_sealed_exam_items(self):
        result = evaluate_parent(self.manifest, ROOT, CHECKPOINT,
                                 device="cpu", batch_size=12)
        self.assertEqual(result["exam_count"], 72)
        self.assertEqual(result["source_token_count"], 222)
        self.assertEqual(result["source_optimizer_step"], 116760)
        self.assertEqual(result["source_manifest_sha256"],
                         self.manifest["manifest_sha256"])
        self.assertEqual(result["exam_rubric_sha256"],
                         self.manifest["exam_rubric_sha256"])
        self.assertEqual(set(result["binary_constrained_predictions"]), {
            "A.IDENTITY", "A.PARENT", "A.LINK", "A.MEMBER", "A.EDGE", "A.MAPS"})
        self.assertEqual(
            sum(x["total"] for x in result["binary_constrained_predictions"].values()), 72)
        self.assertEqual(
            sum(x["correct"] for x in result["binary_constrained_predictions"].values()),
            result["binary_constrained_total_correct"])
        self.assertGreaterEqual(result["binary_constrained_total_correct"], 0)
        self.assertLessEqual(result["binary_constrained_total_correct"], 72)
        self.assertLess(result["mlx_pytorch_max_logit_abs_error"], 0.002)
        self.assertEqual(result["actual_student_optimizer_updates"], 0)
        self.assertTrue(result["source_checkpoint_unchanged"])
        self.assertFalse(result["training_permission_granted"])

    def test_tampered_exam_gold_is_rejected_before_model_evaluation(self):
        broken = deepcopy(self.manifest)
        broken["examination_rows"][0]["gold"] = (
            "FALSE" if broken["examination_rows"][0]["gold"] == "TRUE" else "TRUE")
        with self.assertRaisesRegex(ValueError, "CONTENT_HASH_MISMATCH"):
            evaluate_parent(broken, ROOT, CHECKPOINT)


if __name__ == "__main__":
    unittest.main()
