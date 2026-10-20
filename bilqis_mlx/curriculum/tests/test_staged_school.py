"""A staged grade teaches and assesses constituents before dependent concepts."""
from dataclasses import asdict, replace
import hashlib
import json
import unittest

from bilqis_mlx.curriculum import ExamItem, validate, validate_exam_item
from bilqis_mlx.curriculum.scheduler import assess, assessment_capabilities, start_new, visit
from bilqis_mlx.trainer import _state_from_json
from bilqis_mlx.curriculum.tests.test_school import all_scores, cp, grade_loop, snapshot, three_grade_course


def staged_course():
    course = three_grade_course()
    third = course.grades[-1]
    caps = tuple(replace(cap, prerequisites=(f"c.{i-1}",) if i else ("a.0",))
                 for i, cap in enumerate(third.capabilities))
    third = replace(third, capabilities=caps,
                    teaching_stages=tuple((cap.id,) for cap in caps))
    return replace(course, grades=(*course.grades[:-1], third))


def enter_c(course):
    pointer = cp("whole-student")
    state = start_new(course, pointer)
    # A, initial B, then the required A->B replay, all at one complete student.
    for grade in ("A", "B", "A", "B"):
        assert state.grade == grade
        state = grade_loop(course, state, pointer)
        state = assess(course, state, snapshot(course, pointer,
            all_scores(course, through=grade if grade == "A" and not state.champions else "B")))
    return state, pointer


class StagedSchoolTests(unittest.TestCase):
    def test_canonical_exam_item_requires_explicit_earlier_stage_mastery(self):
        course = staged_course()
        cap = course.grades[-1].capabilities[1]
        item = ExamItem(cap.id, "binary", "TRUE", cap.examined_roots,
                        ("c.0",), cap.independent_oracle, "source-witness")
        with self.assertRaisesRegex(ValueError, "PREREQUISITE"):
            validate_exam_item(course, "C", item, mastered_grade_ids=("A", "B"))
        validate_exam_item(course, "C", item, mastered_grade_ids=("A", "B"),
                           mastered_capability_ids=("c.0",))
        with self.assertRaisesRegex(ValueError, "FUTURE_OR_SAME_STAGE"):
            validate_exam_item(course, "C", item, mastered_grade_ids=("A", "B"),
                               mastered_capability_ids=("c.0", "c.2"))
    def test_future_c_concepts_are_neither_taught_nor_examined(self):
        course = staged_course()
        state, pointer = enter_c(course)
        self.assertEqual(state.queue, ("c.0",))
        allowed = assessment_capabilities(course, state)
        self.assertIn("c.0", allowed)
        self.assertNotIn("c.1", allowed)
        with self.assertRaisesRegex(ValueError, "NOT_NEXT"):
            visit(course, state, "c.1", pointer)

    def test_failed_stage_retries_then_requires_cumulative_constituent_mastery(self):
        course = staged_course()
        state, pointer = enter_c(course)
        epoch = state.grade_exam_epoch
        state = grade_loop(course, state, pointer)
        scores = {c: (7, 8) for c in assessment_capabilities(course, state)}
        state = assess(course, state, snapshot(course, pointer, scores))
        self.assertEqual(state.introduction_stage, 0)
        self.assertEqual(state.grade_exam_epoch, epoch)
        state = grade_loop(course, state, pointer)
        scores = {c: (8, 8) for c in assessment_capabilities(course, state)}
        state = assess(course, state, snapshot(course, pointer, scores))
        self.assertEqual(state.queue, ("c.1",))
        self.assertEqual(state.introduction_stage, 1)
        self.assertEqual(state.grade_exam_epoch, epoch)
        self.assertNotIn("C", state.champions)
        # A past constituent regressing prevents introduction of its dependent.
        state = grade_loop(course, state, pointer)
        scores = {c: (7 if c == "c.0" else 8, 8)
                  for c in assessment_capabilities(course, state)}
        state = assess(course, state, snapshot(course, pointer, scores))
        self.assertEqual(state.introduction_stage, 1)
        self.assertNotIn("c.2", assessment_capabilities(course, state))

    def test_full_c_pass_runs_a_b_c_replay_without_reintroducing_stages(self):
        course = staged_course()
        state, pointer = enter_c(course)
        for stage in range(6):
            state = grade_loop(course, state, pointer)
            scores = {c: (8, 8) for c in assessment_capabilities(course, state)}
            state = assess(course, state, snapshot(course, pointer, scores))
            if stage < 5:
                self.assertEqual(state.introduction_stage, stage+1)
        self.assertEqual(state.grade, "A")
        self.assertEqual(state.revalidation_target_grade, "C")
        for grade in ("A", "B"):
            state = grade_loop(course, state, pointer)
            scores = {c: (8, 8) for c in assessment_capabilities(course, state)}
            state = assess(course, state, snapshot(course, pointer, scores))
        self.assertEqual(state.grade, "C")
        self.assertEqual(state.queue, tuple(f"c.{i}" for i in range(6)))
        self.assertEqual(_state_from_json(json.loads(json.dumps(asdict(state))), course), state)

    def test_forward_or_same_stage_prerequisite_is_invalid(self):
        course = staged_course()
        c = course.grades[-1]
        broken = replace(c, teaching_stages=(("c.0", "c.1"), *c.teaching_stages[2:]))
        with self.assertRaisesRegex(ValueError, "PREREQUISITE"):
            validate(replace(course, grades=(*course.grades[:-1], broken)))

    def test_existing_course_digests_do_not_change_for_unstaged_grades(self):
        course = three_grade_course()
        legacy = asdict(course)
        for grade in legacy["grades"]:
            grade.pop("teaching_stages", None)
        expected = hashlib.sha256(json.dumps(legacy, sort_keys=True,
            separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(course.digest(), expected)
