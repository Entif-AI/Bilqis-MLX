"""Source/assessed-root and prerequisite admission contract."""
from dataclasses import replace
import unittest
from bilqis_mlx.curriculum import (AnswerFamily, BINARY, BOOLEAN_OPERATORS, INT_0_3,
    Capability, Grade, Course, ExamItem, validate, validate_exam_item)


def sample_course():
    def make(prefix, n, difficulty, **options):
        prev = options.get("pre", ())
        composed = options.get("composed", ())
        types = (AnswerFamily("binary", BINARY),)
        if n == 0:
            types += (AnswerFamily("integer_0_3", INT_0_3),)
        return Capability(id=f"{prefix}.{n}", difficulty=difficulty,
            source_anchor="synthetic:fixture-only", taught_roots=(f"root.{prefix}.{n}",),
            examined_roots=(f"root.{prefix}.{n}",), prerequisites=prev,
            composed_of=composed, answer_families=types,
            lesson_generator="synthetic-generator", independent_oracle="synthetic-oracle")
    a = Grade("A", tuple(make("a", i, "basic") for i in range(6)))
    b = Grade("B", tuple(make("b", i, "intermediate",
                      pre=("a.0", "a.1") if i == 0 else (),
                      composed=("a.0", "a.1") if i == 0 else ())
                         for i in range(6)))
    return Course(grades=(a,b), version="synthetic/v1",
                  program_complete=True)


class CourseTests(unittest.TestCase):
    def test_synthetic_course_is_structurally_valid_but_not_executable(self):
        course = sample_course()
        validate(course)
        self.assertFalse(course.executable)
        self.assertEqual(tuple(g.id for g in course.grades), ("A", "B"))
        self.assertEqual(len(course.capability_map), 12)

    def test_exam_accepts_binary_and_integer_and_rejects_unknown_roots(self):
        course = sample_course()
        item = ExamItem("a.0", "integer_0_3", "3", ("root.a.0",), (),
                        "synthetic-oracle", "exam:010")
        validate_exam_item(course, "A", item)
        validate_exam_item(course, "A", replace(item, answer_kind="binary", gold="TRUE"))
        with self.assertRaisesRegex(ValueError, "UNTAUGHT"):
            validate_exam_item(course, "A", replace(item, roots=("root.not.taught",)))
        with self.assertRaisesRegex(ValueError, "ANSWER"):
            validate_exam_item(course, "A", replace(item, gold="4"))

    def test_capability_may_use_bounded_operator_identity_without_fake_binary_family(self):
        course = sample_course()
        a = course.grades[0]
        identified = replace(
            a.capabilities[0],
            answer_families=(AnswerFamily("boolean_operator", BOOLEAN_OPERATORS),),
        )
        course = replace(course, grades=(
            replace(a, capabilities=(identified, *a.capabilities[1:])),
            course.grades[1],
        ))
        validate(course)
        item = ExamItem(
            "a.0", "boolean_operator", "AND", ("root.a.0",), (),
            "synthetic-oracle", "exam:operator",
        )
        validate_exam_item(course, "A", item)
        with self.assertRaisesRegex(ValueError, "ANSWER"):
            validate_exam_item(course, "A", replace(item, gold="XNOR"))
        malformed = replace(
            identified,
            answer_families=(AnswerFamily("boolean_operator", (*BOOLEAN_OPERATORS[:-1], "XNOR")),),
        )
        with self.assertRaisesRegex(ValueError, "BOOLEAN_OPERATOR"):
            validate(replace(course, grades=(
                replace(a, capabilities=(malformed, *a.capabilities[1:])),
                course.grades[1],
            )))

    def test_composed_exam_requires_previously_mastered_grade(self):
        course = sample_course()
        item = ExamItem("b.0", "integer_0_3", "2", ("root.b.0",),
                        ("a.0", "a.1"), "synthetic-oracle", "exam:020")
        with self.assertRaisesRegex(ValueError, "GRADE_NOT_PASSED"):
            validate_exam_item(course, "B", item)
        validate_exam_item(course, "B", item, mastered_grade_ids=("A",))
        with self.assertRaisesRegex(ValueError, "CONSTITUENTS"):
            validate_exam_item(course, "B", replace(item,constituents=()),
                               mastered_grade_ids=("A",))

    def test_same_grade_prerequisite_is_not_an_earlier_grade(self):
        course = sample_course()
        a = course.grades[0]
        bad = replace(a.capabilities[1],prerequisites=("a.0",))
        updated = replace(course,grades=(replace(a,capabilities=(a.capabilities[0],bad)+a.capabilities[2:]),
                                          course.grades[1]))
        with self.assertRaisesRegex(ValueError, "EARLIER_GRADE"):
            validate(updated)

    def test_untaught_root_and_unbalanced_grade_fail_closed(self):
        course = sample_course()
        a = course.grades[0]
        cap = replace(a.capabilities[0],examined_roots=("root.unknown",))
        with self.assertRaisesRegex(ValueError, "UNTAUGHT_ROOT"):
            validate(replace(course,grades=(replace(a,capabilities=(cap,)+a.capabilities[1:]),
                                            course.grades[1])))
        with self.assertRaisesRegex(ValueError, "SIX_TO_NINE"):
            validate(replace(course,grades=(replace(a,capabilities=a.capabilities[:5]),
                                            course.grades[1])))

    def test_per_grade_exam_count_shape_is_guarded(self):
        course = sample_course()
        a = course.grades[0]
        with self.assertRaisesRegex(ValueError, "COUNTS_NOT_BOUND"):
            validate(replace(course, grades=(replace(a, exam_item_counts=(("a.0", 12),)),
                                             course.grades[1])))
        with self.assertRaisesRegex(ValueError, "COUNTS_NOT_BOUND"):
            validate(replace(course, grades=(replace(
                a, exam_item_counts=tuple((f"a.{i}", 0) for i in range(6))),
                course.grades[1])))


if __name__ == "__main__":
    unittest.main()
