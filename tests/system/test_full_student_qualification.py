"""Actual-shape, disposable-only FP32/AdamW continuation regression."""
from pathlib import Path
import sys
import unittest

from bilqis_mlx.full_student_qualification import probe

ROOT = Path(__file__).resolve().parents[2] / "vendor" / "legacy-v16"
SOURCE = ROOT / "runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt"
MANIFEST = Path(__file__).resolve().parents[2] / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"


@unittest.skipUnless(SOURCE.is_file() and MANIFEST.is_file(),
                     "Pinned whole-student/Grade A source archive unavailable")
class FullStudentQualificationTests(unittest.TestCase):
    def test_actual_39_tensor_clone_matches_pytorch_and_survives_restart(self):
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        result = probe(SOURCE, ROOT, grade_a_manifest=MANIFEST,
                       verify_restart=True, device="cpu")
        self.assertEqual(result["start_step"], 116760)
        self.assertEqual(result["torch_step"], 116761)
        self.assertEqual(result["mlx_step"], 116761)
        self.assertEqual(result["tensor_count"], 39)
        self.assertEqual(result["batch_size"], 12)
        self.assertEqual(result["batch_max_sequence_length"], 28)
        self.assertEqual(result["source_graph_token_count"], 222)
        self.assertLess(result["weight_max_abs_delta"], 0.002)
        self.assertLess(result["gradient_max_abs_delta"], 0.002)
        self.assertLess(result["moment_max_abs_delta"], 0.002)
        self.assertEqual(result["disposable_restart"]["weights_abs_delta"], 0)
        self.assertEqual(result["disposable_restart"]["moments_abs_delta"], 0)
        self.assertTrue(result["source_file_unchanged"])
        self.assertEqual(result["neural_updates_to_real_student"], 0)
        self.assertFalse(result["human_training_authorized"])


if __name__ == "__main__":
    unittest.main()
