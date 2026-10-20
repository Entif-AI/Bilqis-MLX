import json
from dataclasses import replace
from pathlib import Path
import unittest

from bilqis_mlx.curriculum.scheduler import (
    start_new, revise_admitted_grade, replace_admitted_grade,
)
from bilqis_mlx.factory.live_releases import (
    initial_course, boolean_successor, minimal_boolean_successor,
)
from bilqis_mlx.boolean_composite import build_course, CAPABILITY
from bilqis_mlx.boolean_identification import build_course as build_identification
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.learning.champions import Checkpoint


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "vendor" / "legacy-v16"


class GradeRevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = json.loads((ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        cls.a = initial_course(accepted_grade_a(manifest))
        cls.old = boolean_successor(cls.a, SOURCE)
        cls.new = build_course(cls.old, SOURCE)
        cls.student = Checkpoint("a" * 64, "bundles/student", 10, True)

    def test_revision_invalidates_revised_grade_champion_but_preserves_student_and_a(self):
        base = start_new(self.old, self.student)
        a_caps = tuple(cap.id for cap in self.old.grades[0].capabilities)
        state = replace(base, champions={"A": self.student, "B": self.student},
                        revalidation_target_grade="B", queue=a_caps)
        revised, grade = revise_admitted_grade(self.old, self.new, state)
        self.assertEqual(grade, "B")
        self.assertEqual(revised.current_student, self.student)
        self.assertEqual(revised.champions, {"A": self.student})
        self.assertIsNone(revised.revalidation_target_grade)
        self.assertEqual(revised.queue, a_caps)
        self.assertEqual(revised.course_digest, self.new.digest())

    def test_revision_while_on_b_reopens_full_b_learning_including_composite(self):
        base = start_new(self.old, self.student)
        b_caps = tuple(cap.id for cap in self.old.grades[-1].capabilities)
        state = replace(base, grade_index=1, champions={"A": self.student, "B": self.student},
                        queue=b_caps)
        revised, _ = revise_admitted_grade(self.old, self.new, state)
        self.assertEqual(revised.grade, "B")
        self.assertIn(CAPABILITY, revised.queue)
        self.assertEqual(revised.queue,
                         tuple(cap.id for cap in self.new.grades[-1].capabilities))
        self.assertNotIn("B", revised.champions)

    def test_replacement_winnows_existing_b_without_touching_student_or_a(self):
        full = build_identification(self.new, SOURCE)
        minimal = minimal_boolean_successor(self.a, SOURCE)
        base = start_new(full, self.student)
        a_caps = tuple(cap.id for cap in full.grades[0].capabilities)
        state = replace(
            base,
            champions={"A": self.student, "B": self.student},
            revalidation_target_grade="B",
            queue=a_caps,
        )
        replaced, grade = replace_admitted_grade(full, minimal, state)
        self.assertEqual(grade, "B")
        self.assertEqual(replaced.current_student, self.student)
        self.assertEqual(replaced.champions, {"A": self.student})
        self.assertEqual(replaced.active_grades, ("A", "B"))
        self.assertEqual(replaced.grade, "A")
        self.assertEqual(replaced.queue, a_caps)
        self.assertIsNone(replaced.revalidation_target_grade)
        self.assertEqual(replaced.course_digest, minimal.digest())

    def test_replacement_can_reduce_pre_composite_full_b_to_minimal_profile(self):
        minimal = minimal_boolean_successor(self.a, SOURCE)
        base = start_new(self.old, self.student)
        state = replace(
            base,
            grade_index=1,
            queue=tuple(cap.id for cap in self.old.grades[-1].capabilities),
            champions={"A": self.student},
        )
        replaced, grade = replace_admitted_grade(self.old, minimal, state)
        self.assertEqual(grade, "B")
        self.assertEqual(replaced.current_student, self.student)
        self.assertEqual(replaced.grade, "B")
        self.assertEqual(replaced.queue, ("B.AND", "B.IFF"))


if __name__ == "__main__":
    unittest.main()
