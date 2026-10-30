"""Source-sealed but *not released* whole-Grade-A item custody."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from bilqis_mlx.grade_a_manifest import build_manifest, verify_manifest
from bilqis_mlx.grade_a_oracle import evaluate

ROOT = Path(__file__).resolve().parents[4] / "vendor" / "legacy-v16"
CHECKPOINT = ROOT / "runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt"


@unittest.skipUnless(CHECKPOINT.is_file(), "Original whole checkpoint not mounted")
class GradeAManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = build_manifest(ROOT, CHECKPOINT)

    def test_216_individual_gold_bearing_source_records(self):
        manifest = self.manifest
        self.assertEqual(manifest["state"], "CANDIDATE_SEALED_NOT_TRAINING_ADMITTED")
        self.assertEqual(len(manifest["training_rows"]), 144)
        self.assertEqual(len(manifest["examination_rows"]), 72)
        self.assertEqual(len({
            row["id"] for row in manifest["training_rows"] + manifest["examination_rows"]
        }), 216)
        self.assertEqual(manifest["parent_student"]["student_vocab_size"], 222)
        self.assertFalse(manifest["training_permission_granted"])
        self.assertFalse(manifest["ni_wordforms_certified"])
        for row in manifest["training_rows"] + manifest["examination_rows"]:
            self.assertEqual(evaluate(row["record"], row["capability"]), row["gold"])
            self.assertEqual(row["answer_kind"], "binary")

    def test_content_digest_and_regeneration_catch_answer_tampering(self):
        verified = verify_manifest(self.manifest, ROOT, CHECKPOINT)
        self.assertEqual(verified["verified_items"], 216)
        self.assertTrue(verified["training_rows_have_gold"])
        changed = deepcopy(self.manifest)
        changed["examination_rows"][0]["gold"] = (
            "FALSE" if changed["examination_rows"][0]["gold"] == "TRUE" else "TRUE"
        )
        with self.assertRaisesRegex(ValueError, "CONTENT_HASH_MISMATCH"):
            verify_manifest(changed, ROOT, CHECKPOINT)
        changed = deepcopy(self.manifest)
        changed["training_permission_granted"] = True
        with self.assertRaisesRegex(ValueError, "IMPROPER_RELEASE_CLAIM"):
            verify_manifest(changed, ROOT, CHECKPOINT)

    def test_committed_candidate_manifest_reproduces_all_exact_source_items(self):
        path = Path(__file__).resolve().parents[4] / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"
        recorded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(recorded, self.manifest)
        self.assertEqual(recorded["exam_rubric_sha256"],
                         "7f351f93b81a1d08a45dd53d5f253ad34c238019015e84284d50ca40378a1370")
        self.assertEqual(verify_manifest(recorded, ROOT, CHECKPOINT)["verified_items"], 216)


if __name__ == "__main__":
    unittest.main()
