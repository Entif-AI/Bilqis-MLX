"""User-owned classroom test lifecycle, with no real student updates."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.runtime.assessment import (
    _candidate_cohort, _generalization_cohort, _grade_test_cohort, _promotion_cohort,
)
from bilqis_mlx.trainer import choose_lesson_batch
from bilqis_mlx.live_grade_a import live_course
from bilqis_mlx.curriculum.scheduler import start_new


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "vendor" / "legacy-v16"


class GradeTestLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        cls.course = live_course(accepted_grade_a(cls.manifest))
        _, _, cls.graph, _, _ = read_sources(SOURCE)

    def receipt(self):
        school = start_new(self.course, Checkpoint("a" * 64, "bundles/inert", 7, True))
        return {"school": asdict(school), "generation": 1, "run_id": "classroom-fixture",
                "source_manifest_sha256": self.manifest["manifest_sha256"]}

    def draw(self, root, receipt):
        return _grade_test_cohort(root, receipt, self.manifest, self.course, SOURCE, self.graph)

    def test_routine_grade_evaluation_redraws_after_each_boundary(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original, pointer = self.draw(root, receipt)
            receipt["qualification_cohort"] = pointer
            receipt["generation"] += 30
            receipt = json.loads(json.dumps(receipt))
            redraw, saved = self.draw(root, receipt)
            self.assertNotEqual(redraw.digest, original.digest)
            self.assertNotEqual(redraw.seed, original.seed)
            self.assertNotEqual(saved["cohort_sha256"], pointer["cohort_sha256"])

    def test_candidate_and_routine_cohorts_both_rotate_independently(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            routine, pointer = self.draw(root, receipt)
            receipt["qualification_cohort"] = pointer
            first = _candidate_cohort(root, receipt, self.manifest,
                                      self.course, SOURCE, self.graph)
            self.assertNotEqual(first.digest, routine.digest)
            receipt["generation"] += 1
            second = _candidate_cohort(root, receipt, self.manifest,
                                       self.course, SOURCE, self.graph)
            self.assertNotEqual(first.digest, second.digest)
            redrawn, redrawn_pointer = self.draw(root, receipt)
            self.assertNotEqual(redrawn.digest, routine.digest)
            self.assertNotEqual(redrawn_pointer["cohort_sha256"], pointer["cohort_sha256"])

    def test_promotion_attempt_is_distinct_and_failed_attempt_remains_fixed(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            routine, _ = self.draw(root, receipt)
            first, first_pointer = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            self.assertNotEqual(first.digest, routine.digest)
            again, again_pointer = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            self.assertEqual(again.digest, first.digest)
            self.assertEqual(again_pointer, first_pointer)
            receipt["qualification_cohort"] = first_pointer
            receipt["generation"] += 1
            second, second_pointer = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            self.assertEqual(second.digest, first.digest)
            self.assertEqual(second_pointer, first_pointer)

    def test_failed_generalization_cohort_is_burned_for_next_qualification(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            promotion, pointer = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            first, first_pointer = _generalization_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph,
                promotion_sha256=promotion.digest)
            self.assertNotEqual(first.digest, promotion.digest)
            receipt["burned_generalization_cohorts"] = [first.digest]
            receipt["generation"] += 1
            second, second_pointer = _generalization_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph,
                promotion_sha256=pointer["cohort_sha256"])
            self.assertNotEqual(second.digest, first.digest)
            self.assertNotEqual(second_pointer["cohort_sha256"], first_pointer["cohort_sha256"])

    def test_burned_generalization_does_not_permanently_embargo_untrained_rows(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            promotion, _ = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            first, _ = _generalization_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph,
                promotion_sha256=promotion.digest)
            receipt["burned_generalization_cohorts"] = [first.digest]
            receipt["generation"] += 1

            replacement = deepcopy(first.rows[0])
            replacement["id"] = "f" * 64
            replacement["source_id"] = replacement["id"]
            overlapping = (replacement, *deepcopy(first.rows[1:]))

            with patch(
                    "bilqis_mlx.runtime.assessment._draw_live_rows",
                    return_value=overlapping):
                second, _ = _generalization_cohort(
                    root, receipt, self.manifest, self.course, SOURCE, self.graph,
                    promotion_sha256=promotion.digest)

            self.assertNotEqual(second.digest, first.digest)
            self.assertNotEqual({row["id"] for row in second.rows},
                                {row["id"] for row in first.rows})
            self.assertGreater(
                len({row["id"] for row in second.rows} &
                    {row["id"] for row in first.rows}),
                0,
            )

    def test_burned_generalization_cannot_repeat_same_specimen_set_under_new_seed(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            promotion, _ = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            first, _ = _generalization_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph,
                promotion_sha256=promotion.digest)
            receipt["burned_generalization_cohorts"] = [first.digest]
            receipt["generation"] += 1

            with patch(
                    "bilqis_mlx.runtime.assessment._draw_live_rows",
                    return_value=deepcopy(first.rows)):
                with self.assertRaisesRegex(
                        ValueError, "FRESH_GENERALIZATION_COHORT_EXHAUSTED"):
                    _generalization_cohort(
                        root, receipt, self.manifest, self.course, SOURCE, self.graph,
                        promotion_sha256=promotion.digest)

    def test_teacher_exposed_generalization_miss_stays_out_of_later_cohort(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            promotion, _ = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            first, _ = _generalization_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph,
                promotion_sha256=promotion.digest)
            receipt["burned_generalization_cohorts"] = [first.digest]
            taught = deepcopy(first.rows[0])
            receipt["teacher_misses"] = [taught]
            receipt["generation"] += 1

            replacement = deepcopy(taught)
            replacement["id"] = "e" * 64
            replacement["source_id"] = replacement["id"]
            candidate = (replacement, *deepcopy(first.rows[1:]))

            with patch(
                    "bilqis_mlx.runtime.assessment._draw_live_rows",
                    return_value=candidate):
                second, _ = _generalization_cohort(
                    root, receipt, self.manifest, self.course, SOURCE, self.graph,
                    promotion_sha256=promotion.digest)

            self.assertNotIn(taught["id"], {row["id"] for row in second.rows})

    def test_generalization_does_not_repeat_promotion_specimen_identities(self):
        receipt = self.receipt()
        receipt["run_id"] = "review-repro"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            promotion, _ = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            fresh, _ = _generalization_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph,
                promotion_sha256=promotion.digest)
            self.assertFalse({row["id"] for row in promotion.rows} &
                             {row["id"] for row in fresh.rows})
            self.assertEqual(len(fresh.rows), 72)
            for cap in self.course.capability_map:
                self.assertEqual(sum(row["capability"] == cap and row["gold"] == "TRUE"
                                     for row in fresh.rows), 6)

    def test_promotion_return_after_another_enrollment_uses_a_new_attempt(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, pointer = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            receipt["qualification_cohort"] = pointer
            receipt["school"]["grade_exam_epoch"] += 1
            receipt["generation"] += 1
            second, _ = _promotion_cohort(
                root, receipt, self.manifest, self.course, SOURCE, self.graph)
            self.assertNotEqual(first.digest, second.digest)

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

    def test_legacy_failed_exam_does_not_freeze_a_new_routine_boundary(self):
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
            redrawn, _ = self.draw(root, receipt)
            self.assertNotEqual(redrawn.digest, cohort.digest)

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
            with self.assertRaisesRegex(ValueError, "COHORT_.*DRIFT"):
                self.draw(root, receipt)


if __name__ == "__main__":
    unittest.main()
