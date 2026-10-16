"""Same-checkpoint grade mastery and two fresh weakest-three recovery rounds."""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.champions import Checkpoint, vote_counts, soup_weights
from bilqis_mlx.school import (Assessment, SchoolState, Score, start_new, visit,
    assess, next_capability, teacher_vote_weights, whole_school_soup_weights,
    continue_after_soup, save_new_state, read_state, weakest_three,
    append_next_grade, verify_state)
from test_curriculum import sample_course


def cp(letter: str, step=100):
    return Checkpoint(hashlib.sha256(letter.encode()).hexdigest(),
                      f"complete-student-{letter}.pt", step, True)


def snapshot(course, checkpoint, answers, *, from_rubric="a"*64):
    return Assessment(checkpoint.sha256, checkpoint.optimizer_step, course.digest(),
                      from_rubric, {key: Score(right, total) for key, (right,total) in answers.items()},
                      evaluation_id="independent-source-panel")


def grade_loop(course, state, candidate):
    while next_capability(state) is not None:
        state = visit(course,state,next_capability(state),candidate)
    return state


def all_scores(course, *, imperfect=(), through=None):
    return {cap.id: (7 if cap.id in imperfect else 8, 8)
            for grade in course.grades if through is None or grade.id <= through
            for cap in grade.capabilities}


def three_grade_course(*, complete=False):
    base = sample_course()
    third = replace(base.grades[1], id="C", capabilities=tuple(
        replace(cap, id=f"c.{i}", difficulty="advanced",
                taught_roots=(f"root.c.{i}",), examined_roots=(f"root.c.{i}",),
                prerequisites=(), composed_of=())
        for i, cap in enumerate(base.grades[1].capabilities)))
    return replace(base, grades=base.grades + (third,),
                   version="synthetic/abc-v1", program_complete=complete)


def four_grade_course():
    base = three_grade_course()
    fourth = replace(base.grades[-1], id="D", capabilities=tuple(
        replace(cap, id=f"d.{i}", difficulty="expert",
                taught_roots=(f"root.d.{i}",), examined_roots=(f"root.d.{i}",))
        for i, cap in enumerate(base.grades[-1].capabilities)))
    return replace(base, grades=base.grades + (fourth,),
                   version="synthetic/abcd-v1")


class SchoolTests(unittest.TestCase):
    def test_still_weak_capabilities_remain_eligible_for_the_second_round(self):
        state = grade_loop(self.course, start_new(self.course, self.init), self.init)
        scores = {f"a.{i}": (i, 8) for i in range(6)}
        first = assess(self.course, state, snapshot(self.course, self.init, scores))
        state = grade_loop(self.course, first, self.init)
        second = assess(self.course, state, snapshot(self.course, self.init, scores))
        self.assertEqual(second.queue, first.queue)

    def setUp(self):
        self.course = sample_course()
        self.init = cp("seed", 116760)

    def test_new_run_always_starts_a_and_no_overwrite_or_implicit_resume(self):
        state = start_new(self.course,self.init)
        self.assertEqual(state.grade,"A")
        self.assertEqual(next_capability(state),"a.0")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/"state.json"
            save_new_state(target,state)
            self.assertEqual(read_state(target,self.course),state)
            with self.assertRaises(FileExistsError):
                save_new_state(target,state)

    def test_two_distinct_weakest_three_rounds_before_returning_to_grade_a(self):
        course = self.course
        state = grade_loop(course,start_new(course,self.init),self.init)
        self.assertEqual(state.stage,"ASSESS_MAIN")
        scores={f"a.{i}":(i,8) for i in range(6)}
        state=assess(course,state,snapshot(course,self.init,scores))
        self.assertEqual(state.stage,"RECOVERY_1")
        self.assertEqual(state.queue,("a.0","a.1","a.2"))
        state=grade_loop(course,state,self.init)
        # Change scores at a new same-step assessment boundary; no stale re-ranking.
        scores={f"a.{i}":(8-i,8) for i in range(6)}
        state=assess(course,state,snapshot(course,self.init,scores))
        self.assertEqual(state.stage,"RECOVERY_2")
        self.assertEqual(state.queue,("a.5","a.4","a.3"))
        state=grade_loop(course,state,self.init)
        state=assess(course,state,snapshot(course,self.init,scores))
        self.assertEqual(state.stage,"MAIN")
        self.assertEqual(state.grade,"A")
        self.assertEqual(state.queue,tuple(f"a.{i}" for i in range(6)))
        self.assertEqual(state.visits,12)

    def test_current_grade_promotion_allows_prior_regression_and_requires_soup(self):
        course=self.course
        a=cp("A",110)
        state=grade_loop(course,start_new(course,self.init),a)
        state=assess(course,state,snapshot(course,a,{f"a.{i}":(8,8) for i in range(6)}))
        self.assertEqual(state.grade,"B")
        self.assertEqual(state.champions["A"],a)
        self.assertEqual(teacher_vote_weights(course,state),{a.sha256:1})
        b=cp("B",120)
        state=grade_loop(course,state,b)
        scores={**{f"a.{i}":(5,8) for i in range(6)},
                **{f"b.{i}":(8,8) for i in range(6)}}
        state=assess(course,state,snapshot(course,b,scores))
        self.assertEqual(state.grade, "A")
        self.assertEqual(state.revalidation_target_grade, "B")
        self.assertEqual(state.stage, "MAIN")
        self.assertEqual(state.champions["A"], a)
        state = grade_loop(course, state, b)
        state = assess(course, state, snapshot(course, b, all_scores(course)))
        self.assertEqual(state.grade, "B")
        state = grade_loop(course, state, b)
        state = assess(course, state, snapshot(
            course, b, all_scores(course, imperfect=("a.0",))))
        self.assertEqual(state.stage,"AWAITING_TEACHER_SOUP")
        self.assertEqual(state.pending_failures,("A",))
        self.assertEqual(state.revalidation_target_grade, None)
        self.assertEqual(state.champions["B"],b)
        self.assertEqual(whole_school_soup_weights(state),{b.sha256:2})
        state=continue_after_soup(course,state,frozen_teacher_receipt="f"*64)
        self.assertEqual(state.school_cycles,2)
        self.assertEqual(state.active_grades,("A",))
        self.assertEqual(state.queue[0],"a.0")
        self.assertEqual(state.current_student,b)

    def test_one_champion_can_repoint_multiple_mastered_grades(self):
        course=self.course
        a=cp("A",200)
        state=grade_loop(course,start_new(course,self.init),a)
        state=assess(course,state,snapshot(course,a,{f"a.{i}":(8,8) for i in range(6)}))
        b=cp("B",210)
        state=grade_loop(course,state,b)
        scores={**{f"a.{i}":(8,8) for i in range(6)},
                **{f"b.{i}":(8,8) for i in range(6)}}
        state=assess(course,state,snapshot(course,b,scores))
        self.assertEqual(state.grade, "A")
        self.assertEqual(state.revalidation_target_grade, "B")
        state = grade_loop(course, state, b)
        state = assess(course, state, snapshot(course, b, scores))
        self.assertEqual(state.grade, "B")
        state = grade_loop(course, state, b)
        state = assess(course, state, snapshot(course, b, scores))
        self.assertEqual(state.stage,"WHOLE_SCHOOL_MASTERED")
        self.assertEqual({x.sha256 for x in state.champions.values()},{b.sha256})
        self.assertEqual(soup_weights(state.champions),{b.sha256:2})

    def test_three_grade_pointers_yield_three_votes_with_one_checkpoint(self):
        shared=cp("shared")
        single=cp("single")
        champions={"A":shared,"B":single,"C":shared,"D":shared}
        self.assertEqual(vote_counts(champions,
                         grade_order=("A","B","C","D","E"),active_grade="E"),
                         {shared.sha256:3,single.sha256:1})
        self.assertEqual(soup_weights(champions),{shared.sha256:3,single.sha256:1})

    def test_no_mixed_step_or_incomplete_snapshot_can_promote(self):
        course=self.course
        state=grade_loop(course,start_new(course,self.init),self.init)
        scores={f"a.{i}":(8,8) for i in range(6)}
        with self.assertRaisesRegex(ValueError,"SAME_CHECKPOINT"):
            assess(course,state,snapshot(course,cp("foreign",999),scores))
        with self.assertRaisesRegex(ValueError,"NOT_COMPLETE"):
            assess(course,state,snapshot(course,self.init,{"a.0":(8,8)}))

    def test_exact_ratio_ranking_not_wrong_count(self):
        scores={"a":Score(7,8),"b":Score(1,2),"c":Score(2,3),"d":Score(0,1)}
        self.assertEqual(weakest_three(scores,tuple(scores)),("d","b","c"))

    def test_rubric_identity_cannot_change_across_student_visits(self):
        course = self.course
        student = self.init
        state = grade_loop(course, start_new(course, student), student)
        imperfect = {f"a.{i}": (5,8) for i in range(6)}
        state = assess(course, state, snapshot(course, student, imperfect))
        self.assertEqual(state.latest_rubric_digest, "a"*64)
        state = grade_loop(course, state, student)
        self.assertEqual(state.latest_rubric_digest, "a"*64)
        with self.assertRaisesRegex(ValueError, "RUBRIC_CHANGED"):
            assess(course, state, snapshot(course, student, imperfect,
                                           from_rubric="b"*64))

    def test_exam_digest_is_bound_to_admitted_course_if_present(self):
        sealed_a = replace(self.course.grades[0], assessment_sha256="c"*64)
        course = replace(self.course, grades=(sealed_a, self.course.grades[1]))
        student = self.init
        state = grade_loop(course, start_new(course, student), student)
        perfect = {f"a.{i}": (8,8) for i in range(6)}
        with self.assertRaisesRegex(ValueError, "GRADE_SEALED_RUBRIC"):
            assess(course, state, snapshot(course, student, perfect))
        moved = assess(course, state, snapshot(course, student, perfect,
                                             from_rubric="c"*64))
        self.assertEqual(moved.grade, "B")

    def test_next_grade_may_use_new_cumulative_rubric_without_mutating_a(self):
        a, b = self.course.grades
        course = replace(self.course,
                         grades=(replace(a, assessment_sha256="a"*64),
                                 replace(b, assessment_sha256="b"*64)),
                         assessment_manifest_sha256="b"*64)
        student = cp("advanced", 119000)
        state = grade_loop(course, start_new(course, self.init), student)
        state = assess(course, state, snapshot(
            course, student, {f"a.{i}": (8,8) for i in range(6)}))
        self.assertEqual(state.grade, "B")
        self.assertIsNone(state.latest_rubric_digest)
        state = grade_loop(course, state, student)
        scores = {**{f"a.{i}": (8,8) for i in range(6)},
                  **{f"b.{i}": (8,8) for i in range(6)}}
        with self.assertRaisesRegex(ValueError, "GRADE_SEALED_RUBRIC"):
            assess(course, state, snapshot(course, student, scores,
                                           from_rubric="a"*64))
        state = assess(course, state, snapshot(course, student, scores,
                                               from_rubric="b"*64))
        self.assertEqual(state.revalidation_target_grade, "B")
        self.assertEqual(state.grade, "A")
        state = grade_loop(course, state, student)
        state = assess(course, state, snapshot(course, student, scores,
                                               from_rubric="b"*64))
        state = grade_loop(course, state, student)
        state = assess(course, state, snapshot(course, student, scores,
                                               from_rubric="b"*64))
        self.assertEqual(state.stage, "WHOLE_SCHOOL_MASTERED")

    def test_b_graduation_revalidates_a_then_b_before_starting_c(self):
        course = three_grade_course()
        a, b, reviewed = cp("A",110), cp("B",120), cp("reviewed",130)
        state = grade_loop(course, start_new(course,self.init), a)
        state = assess(course, state, snapshot(course, a, {
            f"a.{i}": (8,8) for i in range(6)}))
        state = grade_loop(course, state, b)
        state = assess(course, state, snapshot(course, b,
            {**{f"a.{i}": (7,8) for i in range(6)},
             **{f"b.{i}": (8,8) for i in range(6)}}))
        self.assertEqual((state.grade,state.revalidation_target_grade), ("A","B"))
        self.assertEqual(state.queue, tuple(f"a.{i}" for i in range(6)))
        self.assertEqual(teacher_vote_weights(course,state),
                         {a.sha256:1,b.sha256:1})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mid-revalidation.json"
            save_new_state(path, state)
            state = read_state(path, course)
        self.assertEqual(state.revalidation_target_grade, "B")
        state = grade_loop(course, state, reviewed)
        state = assess(course, state, snapshot(course, reviewed,
            all_scores(course, through="B")))
        self.assertEqual((state.grade,state.revalidation_target_grade), ("B","B"))
        state = grade_loop(course, state, reviewed)
        state = assess(course, state, snapshot(course, reviewed,
            all_scores(course, through="B")))
        self.assertEqual((state.grade,state.stage), ("C","MAIN"))
        self.assertIsNone(state.revalidation_target_grade)
        self.assertEqual(state.champions["A"], reviewed)
        self.assertEqual(state.champions["B"], reviewed)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "school.json"
            save_new_state(path, state)
            self.assertEqual(read_state(path, course), state)

    def test_c_graduation_revalidates_a_b_c_before_waiting_for_d(self):
        course = three_grade_course()
        students = (cp("A"), cp("B"), cp("recheck-B"), cp("C"), cp("recheck-C"))
        state = grade_loop(course, start_new(course, self.init), students[0])
        state = assess(course, state, snapshot(course, students[0], {
            f"a.{i}": (8,8) for i in range(6)}))
        state = grade_loop(course, state, students[1])
        state = assess(course, state, snapshot(course, students[1],
            {**{f"a.{i}": (8,8) for i in range(6)},
             **{f"b.{i}": (8,8) for i in range(6)}}))
        for grade in ("A", "B"):
            self.assertEqual(state.grade, grade)
            state = grade_loop(course, state, students[2])
            state = assess(course, state, snapshot(course, students[2],
                {**{f"a.{i}": (8,8) for i in range(6)},
                 **{f"b.{i}": (8,8) for i in range(6)}}))
        self.assertEqual(state.grade, "C")
        state = grade_loop(course, state, students[3])
        state = assess(course, state, snapshot(course, students[3], all_scores(course)))
        self.assertEqual(state.revalidation_target_grade, "C")
        for grade in ("A", "B", "C"):
            self.assertEqual(state.grade, grade)
            state = grade_loop(course, state, students[4])
            state = assess(course, state, snapshot(course, students[4], all_scores(course)))
        self.assertEqual(state.stage, "AWAITING_NEXT_GRADE")
        self.assertIsNone(state.revalidation_target_grade)
        self.assertEqual(set(state.champions), {"A", "B", "C"})

    def test_prefix_sweep_extends_generically_through_grade_d(self):
        course = four_grade_course()
        state = start_new(course, self.init)
        for index, grade in enumerate("ABCD"):
            self.assertEqual(state.grade, grade)
            model = cp(grade, step=200+index)
            state = grade_loop(course, state, model)
            state = assess(course, state, snapshot(
                course, model, all_scores(course, through=grade)))
            if index:
                self.assertEqual(state.revalidation_target_grade, grade)
                for earlier in "ABCD"[:index+1]:
                    self.assertEqual(state.grade, earlier)
                    state = grade_loop(course, state, model)
                    state = assess(course, state, snapshot(
                        course, model, all_scores(course, through=grade)))
            if index < 3:
                self.assertEqual(state.grade, "ABCD"[index+1])
                self.assertIsNone(state.revalidation_target_grade)
        self.assertEqual(state.stage, "AWAITING_NEXT_GRADE")
        self.assertEqual({c.sha256 for c in state.champions.values()}, {model.sha256})

    def test_regression_in_last_review_checkpoint_restarts_prefix_not_c(self):
        course = three_grade_course()
        model = self.init
        state = grade_loop(course, start_new(course, model), model)
        state = assess(course, state, snapshot(course, model,
            {f"a.{i}": (8,8) for i in range(6)}))
        state = grade_loop(course, state, model)
        state = assess(course, state, snapshot(course, model,
            {**{f"a.{i}": (8,8) for i in range(6)},
             **{f"b.{i}": (8,8) for i in range(6)}}))
        state = grade_loop(course, state, model)
        state = assess(course, state, snapshot(course, model,
            {**{f"a.{i}": (8,8) for i in range(6)},
             **{f"b.{i}": (8,8) for i in range(6)}}))
        state = grade_loop(course, state, model)
        state = assess(course, state, snapshot(course, model,
            {**{f"a.{i}": (7,8) for i in range(6)},
             **{f"b.{i}": (8,8) for i in range(6)}}))
        self.assertEqual((state.grade, state.stage, state.revalidation_target_grade),
                         ("A", "MAIN", "B"))
        state = grade_loop(course, state, model)
        scores = {**{f"a.{i}": (8,8) for i in range(6)},
                  **{f"b.{i}": (8,8) for i in range(6)}}
        state = assess(course, state, snapshot(course, model, scores))
        state = grade_loop(course, state, model)
        state = assess(course, state, snapshot(course, model, scores))
        self.assertEqual(state.grade, "C")
        self.assertIsNone(state.revalidation_target_grade)

    def test_legacy_v1_state_without_revalidation_field_still_reads(self):
        course = self.course
        legacy = asdict(start_new(course, self.init))
        self.assertNotEqual(legacy.pop("revalidation_target_grade", None), "B")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prior-v1.json"
            path.write_text(json.dumps(legacy), encoding="utf-8")
            restored = read_state(path, course)
        self.assertIsNone(restored.revalidation_target_grade)

    def test_cannot_forge_revalidation_target_or_skip_prior_grade(self):
        course = three_grade_course()
        state = start_new(course, self.init)
        with self.assertRaisesRegex(ValueError, "REVALIDATION"):
            verify_state(course, replace(state, revalidation_target_grade="C"))
        a, b = cp("a"), cp("b")
        state = grade_loop(course, state, a)
        state = assess(course, state, snapshot(course, a,
            {f"a.{i}": (8,8) for i in range(6)}))
        state = grade_loop(course, state, b)
        state = assess(course, state, snapshot(course, b,
            all_scores(course, through="B")))
        with self.assertRaisesRegex(ValueError, "REVALIDATION"):
            verify_state(course, replace(state, grade_index=2))

    def test_revalidation_a_failure_uses_full_two_weakest_three_rounds(self):
        course = three_grade_course()
        student = self.init
        state = grade_loop(course, start_new(course, student), student)
        state = assess(course, state, snapshot(course, student,
            all_scores(course, through="A")))
        state = grade_loop(course, state, student)
        state = assess(course, state, snapshot(course, student,
            all_scores(course, through="B")))
        self.assertEqual(state.revalidation_target_grade, "B")
        state = grade_loop(course, state, student)
        imperfect = all_scores(course, through="B", imperfect=("a.0", "a.1"))
        state = assess(course, state, snapshot(course, student, imperfect))
        self.assertEqual(state.stage, "RECOVERY_1")
        self.assertEqual(state.queue[:2], ("a.0", "a.1"))
        self.assertEqual(state.revalidation_target_grade, "B")
        state = grade_loop(course, state, student)
        state = assess(course, state, snapshot(course, student, imperfect))
        self.assertEqual(state.stage, "RECOVERY_2")
        self.assertFalse(set(state.queue) & set(state.first_recovery))
        self.assertEqual(state.revalidation_target_grade, "B")

    def test_admitted_grade_rejects_fabricated_one_question_perfect_score(self):
        grade = replace(self.course.grades[0],
                        exam_item_counts=tuple((f"a.{i}", 12) for i in range(6)))
        course = replace(self.course, grades=(grade, self.course.grades[1]))
        state = grade_loop(course, start_new(course, self.init), self.init)
        with self.assertRaisesRegex(ValueError, "SEALED_ITEM_COUNT"):
            assess(course, state, snapshot(
                course, self.init, {f"a.{i}": (1,1) for i in range(6)}))
        moved = assess(course, state, snapshot(
            course, self.init, {f"a.{i}": (12,12) for i in range(6)}))
        self.assertEqual(moved.grade, "B")

    def test_partial_grade_a_waits_and_future_grade_appends_without_relearning(self):
        full = self.course
        a = replace(full.grades[0], assessment_sha256="a"*64)
        a_only = replace(full, grades=(a,), version="partial-A/v1",
                         program_complete=False, assessment_manifest_sha256="a"*64)
        student = cp("human-A", 116800)
        state = grade_loop(a_only, start_new(a_only, self.init), student)
        state = assess(a_only, state, snapshot(
            a_only, student, {f"a.{i}": (12,12) for i in range(6)}))
        self.assertEqual(state.stage, "AWAITING_NEXT_GRADE")
        self.assertNotEqual(state.stage, "WHOLE_SCHOOL_MASTERED")
        self.assertEqual(state.champions["A"], student)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "a-only.json"
            save_new_state(target, state)
            self.assertEqual(read_state(target, a_only), state)
            # B was not appended by simply passing a different course digest.
            successor = replace(full, grades=(a, full.grades[1]),
                                version="partial-A-plus-B/v2", program_complete=False,
                                assessment_manifest_sha256="b"*64)
            with self.assertRaisesRegex(ValueError, "DRIFTED"):
                read_state(target, successor)
        resumed = append_next_grade(a_only, successor, state)
        self.assertEqual(resumed.grade, "B")
        self.assertEqual(resumed.queue, tuple(f"b.{i}" for i in range(6)))
        self.assertEqual(resumed.champions["A"], student)
        self.assertEqual(resumed.current_student, student)
        self.assertEqual(resumed.latest_rubric_digest, None)
        with self.assertRaisesRegex(ValueError, "DRIFTED"):
            append_next_grade(a_only, successor, resumed)
        with self.assertRaisesRegex(ValueError, "CHANGE_PREVIOUS_GRADE"):
            changed_a = replace(a, assessment_sha256="c"*64)
            append_next_grade(a_only, replace(successor, grades=(changed_a, full.grades[1])),
                              state)


if __name__=="__main__":
    unittest.main()

class WholeStudentSelectionTests(unittest.TestCase):
    def test_best_complete_candidate_by_same_full_rubric_not_latest_step(self):
        course=sample_course()
        older=cp("older",100)
        newer=cp("newer",10000)
        pool={**{f"a.{i}":(8,8) for i in range(6)},
              **{f"b.{i}":(7,8) for i in range(6)}}
        from bilqis_mlx.school import choose_best_whole_student
        oldscore=snapshot(course,older,pool)
        newscore=snapshot(course,newer,{k:(v-2,t) for k,(v,t) in pool.items()})
        result=choose_best_whole_student(course,
                 ((older,oldscore),(newer,newscore)),("A","B"))
        self.assertEqual(result,older)
        self.assertTrue(result.model_and_native_adamw)

    def test_different_rubrics_cannot_compare_candidate_pools(self):
        course=sample_course()
        a,b=cp("a"),cp("b")
        pool={f"a.{i}":(8,8) for i in range(6)}
        from bilqis_mlx.school import choose_best_whole_student
        with self.assertRaisesRegex(ValueError,"NOT_COMPARABLE"):
            choose_best_whole_student(course,
               ((a,snapshot(course,a,pool)),
                (b,snapshot(course,b,pool,from_rubric="b"*64))), ("A",))
