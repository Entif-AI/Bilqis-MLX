"""User-owned classroom test lifecycle, with no real student updates."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.champions import Checkpoint
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.grade_a_trainer import (
    _candidate_cohort, _grade_test_cohort, choose_lesson_batch,
)
from bilqis_mlx.live_grade_a import live_course
from bilqis_mlx.school import start_new


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "bilqis-triplets-v16"


class GradeTestLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "docs/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        cls.course = live_course(accepted_grade_a(cls.manifest))
        _, _, cls.graph, _, _ = read_sources(SOURCE)

    def receipt(self):
        school = start_new(self.course, Checkpoint("a" * 64, "bundles/inert", 7, True))
        return {"school": asdict(school), "generation": 1, "run_id": "classroom-fixture",
                "source_manifest_sha256": self.manifest["manifest_sha256"]}

    def draw(self, root, receipt):
        return _grade_test_cohort(root, receipt, self.manifest, self.course, SOURCE, self.graph)

    def test_failed_retries_and_reload_keep_questions_seed_and_criteria(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, pointer = self.draw(root, receipt)
            receipt["qualification_cohort"] = pointer
            receipt["generation"] += 30
            receipt = json.loads(json.dumps(receipt))
            with patch("bilqis_mlx.grade_a_trainer._draw_live_rows",
                       side_effect=AssertionError("Retry redrew its test")):
                retry, saved = self.draw(root, receipt)
            self.assertEqual(retry, original)
            self.assertEqual(saved, pointer)

    def test_candidate_cohort_rotates_without_changing_graduation_exam(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            graduation, pointer = self.draw(root, receipt)
            receipt["qualification_cohort"] = pointer
            first = _candidate_cohort(root, receipt, self.manifest,
                                      self.course, SOURCE, self.graph)
            self.assertNotEqual(first.digest, graduation.digest)
            receipt["generation"] += 1
            second = _candidate_cohort(root, receipt, self.manifest,
                                       self.course, SOURCE, self.graph)
            self.assertNotEqual(first.digest, second.digest)
            with patch("bilqis_mlx.grade_a_trainer._draw_live_rows",
                       side_effect=AssertionError("Graduation exam was redrawn")):
                stable, stable_pointer = self.draw(root, receipt)
            self.assertEqual(stable.digest, graduation.digest)
            self.assertEqual(stable_pointer, pointer)

    def test_returning_to_the_same_grade_gets_new_questions(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, pointer = self.draw(root, receipt)
            receipt["qualification_cohort"] = pointer
            receipt["school"]["grade_exam_epoch"] += 1
            receipt["generation"] += 1
            revisited, _ = self.draw(root, receipt)
            self.assertNotEqual(revisited.digest, original.digest)
            self.assertNotEqual(revisited.seed, original.seed)

    def test_current_legacy_failed_exam_is_adopted_without_redraw(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cohort, pointer = self.draw(root, receipt)
            receipt["school"].pop("grade_exam_epoch")
            receipt["last_exam"] = {key: pointer[key] for key in (
                "cohort_sha256", "cohort_seed", "cohort_file")}
            receipt["last_exam"].update(
                exam_rubric_sha256=self.course.grades[0].assessment_sha256,
                scores={c.id: {"correct": 0, "total": 12}
                        for c in self.course.grades[0].capabilities})
            receipt["generation"] += 1
            with patch("bilqis_mlx.grade_a_trainer._draw_live_rows",
                       side_effect=AssertionError("Existing failed grade test was discarded")):
                adopted, _ = self.draw(root, receipt)
            self.assertEqual(adopted, cohort)

    def test_exam_constructions_remain_eligible_for_teaching(self):
        with tempfile.TemporaryDirectory() as temp:
            cohort, _ = self.draw(Path(temp), self.receipt())
            rows = list(cohort.rows)
            batch = choose_lesson_batch(rows, {"depth": 1, "contrast": 1.0}, 18, batch_size=8)
            self.assertEqual(len(batch), 8)
            self.assertTrue({r["id"] for r in batch} <= {r["id"] for r in rows})

    def test_changed_question_content_is_rejected_without_replacing_exam(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, pointer = self.draw(root, receipt)
            receipt["qualification_cohort"] = pointer
            path = root / pointer["cohort_file"]
            payload = json.loads(path.read_text())
            payload["rows"][0]["gold"] = "FALSE" if payload["rows"][0]["gold"] == "TRUE" else "TRUE"
            path.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "COHORT_CONTENT_DRIFT"):
                self.draw(root, receipt)


if __name__ == "__main__":
    unittest.main()
