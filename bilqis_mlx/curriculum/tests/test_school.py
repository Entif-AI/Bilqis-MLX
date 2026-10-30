"""Same-checkpoint grade mastery and two fresh weakest-three recovery rounds."""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.learning.champions import Checkpoint, vote_counts, soup_weights
from bilqis_mlx.curriculum.scheduler import (Assessment, SchoolState, Score, start_new, visit,
    assess, assess_withheld, next_capability, reactivate_stagnation_debt,
    teacher_vote_weights, whole_school_soup_weights,
    continue_after_soup, save_new_state, read_state, weakest_three,
    append_next_grade, verify_state, require_assessment_after_flash, assess_flash,
    assessment_capabilities)
from bilqis_mlx.curriculum.tests.test_curriculum import sample_course


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


def settle_promotion_sweep(course, state, candidate, answers, *,
                           from_rubric="a"*64):
    while state.stage == "PROMOTION_SWEEP":
        state = visit(course, state, next_capability(state), candidate)
        state = assess(
            course, state,
            snapshot(course, candidate, answers, from_rubric=from_rubric))
    return state


def assess_and_settle(course, state, candidate, answers, *,
                      from_rubric="a"*64):
    state = assess(
        course, state,
        snapshot(course, candidate, answers, from_rubric=from_rubric))
    return settle_promotion_sweep(
        course, state, candidate, answers, from_rubric=from_rubric)


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


def sealed_three_grade_course(*, complete=False):
    course = three_grade_course(complete=complete)
    seals = ("a" * 64, "b" * 64, "c" * 64)
    grades = tuple(replace(grade, assessment_sha256=seal)
                   for grade, seal in zip(course.grades, seals))
    return replace(course, grades=grades, assessment_manifest_sha256=seals[-1])


def four_grade_course():
    base = three_grade_course()
    fourth = replace(base.grades[-1], id="D", capabilities=tuple(
        replace(cap, id=f"d.{i}", difficulty="expert",
                taught_roots=(f"root.d.{i}",), examined_roots=(f"root.d.{i}",))
        for i, cap in enumerate(base.grades[-1].capabilities)))
    return replace(base, grades=base.grades + (fourth,),
                   version="synthetic/abcd-v1")


class SchoolTests(unittest.TestCase):
    def test_stable_above_ninety_two_grade_mean_enters_next_grade_with_debt(self):
        course = self.course
        student = cp("mean-promoted-A", 105)
        state = grade_loop(course, start_new(course, self.init), student)
        scores = {f"a.{i}": (8, 8) for i in range(6)}
        scores["a.0"] = (5, 8)

        state = assess_and_settle(course, state, student, scores)

        self.assertEqual((state.grade, state.stage), ("B", "MAIN"))
        self.assertEqual(state.carried_mastery_debt, ("a.0",))
        self.assertNotIn("A", state.champions)

    def test_stable_above_ninety_two_partial_grade_waits_at_debt_boundary(self):
        full = self.course
        a_only = replace(
            full, grades=(full.grades[0],), version="partial-A-mean/v1",
            program_complete=False,
            assessment_manifest_sha256=full.grades[0].assessment_sha256)
        student = cp("mean-promoted-partial-A", 106)
        state = grade_loop(a_only, start_new(a_only, self.init), student)
        scores = {f"a.{i}": (8, 8) for i in range(6)}
        scores["a.0"] = (5, 8)

        state = assess_and_settle(a_only, state, student, scores)

        self.assertEqual(state.stage, "AWAITING_NEXT_GRADE_WITH_DEBT")
        self.assertEqual(state.carried_mastery_debt, ("a.0",))
        self.assertNotIn("A", state.champions)

    def test_school_state_drift_reports_the_failed_identity_predicate(self):
        course = three_grade_course()
        state = start_new(course, self.init)
        drifted = replace(state, course_digest="0" * 64)

        with self.assertRaisesRegex(
                ValueError,
                r"SCHOOL.STATE.COURSE_DIGEST_MISMATCH"):
            verify_state(course, drifted)

    def test_full_imperfect_grade_sweep_precedes_global_two_round_recovery(self):
        course = three_grade_course()
        student = self.init
        state = replace(
            start_new(course, student),
            champions={grade: student for grade in ("A", "B", "C")},
            revalidation_target_grade="C",
        )
        imperfect = all_scores(course, imperfect=("a.0", "b.0", "c.0"))

        state = grade_loop(course, state, student)
        state = assess(course, state, snapshot(course, student, imperfect))
        self.assertEqual((state.grade, state.stage), ("B", "MAIN"))

        state = grade_loop(course, state, student)
        state = assess(course, state, snapshot(course, student, imperfect))
        self.assertEqual((state.grade, state.stage), ("C", "MAIN"))

        state = grade_loop(course, state, student)
        state = assess(course, state, snapshot(course, student, imperfect))
        self.assertEqual(state.stage, "RECOVERY_1")
        self.assertEqual(state.queue, ("a.0", "b.0", "c.0"))

        state = grade_loop(course, state, student)
        state = assess(course, state, snapshot(course, student, imperfect))
        self.assertEqual(state.stage, "RECOVERY_2")
        self.assertEqual(state.queue, ("a.0", "b.0", "c.0"))

        state = grade_loop(course, state, student)
        state = assess(course, state, snapshot(course, student, imperfect))
        self.assertEqual((state.grade, state.stage), ("A", "MAIN"))

    def test_flash_uses_same_full_grade_sweep_before_global_recovery(self):
        course = three_grade_course()
        student = self.init
        state = replace(
            start_new(course, student),
            champions={grade: student for grade in ("A", "B", "C")},
            revalidation_target_grade="C",
        )
        imperfect = all_scores(course, imperfect=("a.0", "b.0", "c.0"))

        state = grade_loop(course, state, student)
        state = assess_flash(course, state, snapshot(course, student, imperfect))
        self.assertEqual((state.grade, state.stage), ("B", "MAIN"))

        state = grade_loop(course, state, student)
        state = assess_flash(course, state, snapshot(course, student, imperfect))
        self.assertEqual((state.grade, state.stage), ("C", "MAIN"))

        state = grade_loop(course, state, student)
        state = assess_flash(course, state, snapshot(course, student, imperfect))
        self.assertEqual(state.stage, "RECOVERY_1")

    def test_perfect_a_is_skipped_while_b_and_c_sweep_before_recovery(self):
        course = three_grade_course()
        student = self.init
        b = course.grades[1]
        state = replace(
            start_new(course, student),
            grade_index=1,
            introduction_stage=(len(b.teaching_stages) - 1 if b.teaching_stages else 0),
            champions={grade: student for grade in ("A", "B", "C")},
            revalidation_target_grade="C",
        )
        imperfect = all_scores(course, imperfect=("b.0", "c.0"))

        state = grade_loop(course, state, student)
        state = assess(course, state, snapshot(course, student, imperfect))
        self.assertEqual((state.grade, state.stage), ("C", "MAIN"))

        state = grade_loop(course, state, student)
        state = assess(course, state, snapshot(course, student, imperfect))
        self.assertEqual(state.stage, "RECOVERY_1")
        self.assertEqual(state.queue, ("b.0", "c.0"))

    def test_flash_stop_restores_assessment_debt(self):
        state = start_new(self.course, self.init)
        partial = visit(self.course, state, state.queue[0], self.init)

        due = require_assessment_after_flash(self.course, partial)

        self.assertEqual(due.stage, "ASSESS_MAIN")
        self.assertEqual(due.queue, ())
        self.assertEqual(due.champions, partial.champions)
        self.assertEqual(due.grade_exam_epoch, partial.grade_exam_epoch)

    def test_flash_scheduler_assessment_advances_after_second_recovery_without_authority(self):
        course = three_grade_course()
        student = self.init
        base = start_new(course, student)
        b = course.grades[1]
        state = replace(
            base,
            grade_index=1,
            introduction_stage=(len(b.teaching_stages) - 1 if b.teaching_stages else 0),
            stage="ASSESS_RECOVERY_2",
            queue=(),
            first_recovery=("b.0",),
            champions={grade: student for grade in ("A", "B", "C")},
            revalidation_target_grade="C",
        )
        verify_state(course, state)
        imperfect = all_scores(course, imperfect=("b.0", "c.0"))
        before_champions = dict(state.champions)
        before_epoch = state.grade_exam_epoch

        moved = assess_flash(course, state, snapshot(course, student, imperfect))

        self.assertEqual(moved.grade, "C")
        self.assertEqual(moved.stage, "MAIN")
        self.assertEqual(moved.queue, tuple(cap.id for cap in course.grades[2].capabilities))
        self.assertEqual(moved.champions, before_champions)
        self.assertEqual(moved.grade_exam_epoch, before_epoch)

    def test_flash_scheduler_holds_all_perfect_checkpoint_for_authoritative_exam(self):
        course = three_grade_course()
        student = self.init
        base = start_new(course, student)
        b = course.grades[1]
        state = replace(
            base,
            grade_index=1,
            introduction_stage=(len(b.teaching_stages) - 1 if b.teaching_stages else 0),
            stage="ASSESS_RECOVERY_2",
            queue=(),
            first_recovery=("b.0",),
            champions={grade: student for grade in ("A", "B", "C")},
            revalidation_target_grade="C",
        )
        perfect = all_scores(course)

        held = assess_flash(course, state, snapshot(course, student, perfect))

        self.assertEqual(held.grade, "B")
        self.assertEqual(held.stage, "ASSESS_RECOVERY_2")
        self.assertEqual(held.queue, ())
        self.assertEqual(held.champions, state.champions)
        self.assertEqual(held.grade_exam_epoch, state.grade_exam_epoch)

    def test_withheld_capability_remains_mastery_debt_while_healthy_work_continues(self):
        state = grade_loop(self.course, start_new(self.course, self.init), self.init)
        active = {f"a.{i}": (8, 8) for i in range(1, 6)}
        active["a.1"] = (7, 8)
        reduced = assess_withheld(
            self.course, state, snapshot(self.course, self.init, active),
            ("a.0",))
        self.assertEqual(reduced.stage, "RECOVERY_1")
        self.assertEqual(reduced.queue, ("a.1",))
        self.assertNotIn("A", reduced.champions)

    def test_withheld_entire_later_grade_keeps_cumulative_rubric_authority(self):
        a, b = self.course.grades
        course = replace(
            self.course,
            grades=(replace(a, assessment_sha256="a" * 64),
                    replace(b, assessment_sha256="b" * 64)),
            assessment_manifest_sha256="b" * 64,
        )
        student = self.init
        state = replace(
            start_new(course, student),
            stage="ASSESS_RECOVERY_2",
            champions={"A": student},
            latest_rubric_digest="b" * 64,
            main_sweep_visited=("B", "A"),
        )
        self.assertEqual(
            set(assessment_capabilities(course, state)),
            {*(f"a.{i}" for i in range(6)), *(f"b.{i}" for i in range(6))},
        )
        active = {f"a.{i}": (8, 8) for i in range(6)}
        deferred = assess_withheld(
            course,
            state,
            snapshot(course, student, active, from_rubric="b" * 64),
            tuple(f"b.{i}" for i in range(6)),
        )
        self.assertEqual(deferred.stage, "DEFERRED_STAGNATION")
        self.assertEqual(deferred.latest_rubric_digest, "b" * 64)
        self.assertEqual(deferred.champions, {"A": student})

    def test_only_withheld_debt_stops_for_review_and_reenters_next_run(self):
        state = grade_loop(self.course, start_new(self.course, self.init), self.init)
        active = {f"a.{i}": (8, 8) for i in range(1, 6)}
        deferred = assess_withheld(
            self.course, state, snapshot(self.course, self.init, active),
            ("a.0",))
        self.assertEqual(deferred.stage, "DEFERRED_STAGNATION")
        self.assertEqual(deferred.queue, ())
        self.assertNotIn("A", deferred.champions)
        reentered = reactivate_stagnation_debt(self.course, deferred, ("a.0",))
        self.assertEqual(reentered.stage, "RECOVERY_1")
        self.assertEqual(reentered.queue, ("a.0",))

    def test_withheld_staged_grade_entry_does_not_hide_other_imperfect_grades(self):
        course = three_grade_course()
        c = course.grades[-1]
        c = replace(c, teaching_stages=tuple((cap.id,) for cap in c.capabilities))
        course = replace(course, grades=(*course.grades[:-1], c))
        all_c = tuple(cap.id for cap in c.capabilities)
        state = replace(
            start_new(course, self.init),
            grade_index=1,
            stage="ASSESS_RECOVERY_2",
            queue=(),
            first_recovery=("b.0",),
            carried_mastery_debt=all_c,
            main_sweep_visited=("A", "B"),
        )
        withheld = ("c.0",)
        self.assertNotIn("c.1", assessment_capabilities(course, state))
        active = {
            cap: (8, 8)
            for cap in assessment_capabilities(course, state)
            if cap not in withheld
        }
        active["a.0"] = (7, 8)
        active["b.0"] = (7, 8)

        continued = assess_withheld(
            course, state, snapshot(course, self.init, active), withheld)

        self.assertEqual((continued.grade, continued.stage), ("A", "MAIN"))
        self.assertIn("a.0", continued.queue)
        self.assertNotEqual(continued.stage, "DEFERRED_STAGNATION")

    def test_trainer_auto_rehabilitates_when_one_grade_is_the_only_debt_left(self):
        from bilqis_mlx import trainer as trainer
        from bilqis_mlx.learning.stagnation_control import (
            quarantined_capabilities, start_session)

        state = grade_loop(self.course, start_new(self.course, self.init), self.init)
        active = {f"a.{i}": (8, 8) for i in range(1, 6)}
        deferred = assess_withheld(
            self.course, state, snapshot(self.course, self.init, active),
            ("a.0",))
        control = start_session(
            session_id="fixture-command", generation=20,
            required_capabilities=tuple(f"a.{i}" for i in range(6)))
        control["quarantined"] = {
            "a.0": {"capability": "a.0", "reason": "fixture"},
        }

        control, resumed, events = trainer._rehabilitate_sole_grade_debt(
            self.course, deferred, control, ("a.0",), generation=21)
        self.assertEqual(resumed.stage, "RECOVERY_1")
        self.assertEqual(resumed.queue, ("a.0",))
        self.assertEqual(quarantined_capabilities(control), ())
        self.assertEqual(
            events[0]["event"], "SCHOOL_STAGNATION_REHABILITATION_STARTED")

    def test_trainer_does_not_auto_rehabilitate_mixed_grade_debt(self):
        from bilqis_mlx import trainer as trainer
        from bilqis_mlx.learning.stagnation_control import start_session

        course = three_grade_course()
        state = start_new(course, self.init)
        state = replace(
            state, stage="DEFERRED_STAGNATION", queue=(), first_recovery=())
        debt = ("a.0", "b.0")
        control = start_session(
            session_id="fixture-command", generation=20,
            required_capabilities=tuple(
                cap.id for grade in course.grades for cap in grade.capabilities))
        control["quarantined"] = {
            capability: {"capability": capability, "reason": "fixture"}
            for capability in debt
        }

        unchanged_control, unchanged_state, events = (
            trainer._rehabilitate_sole_grade_debt(
                course, state, control, debt, generation=21))
        self.assertIs(unchanged_control, control)
        self.assertIs(unchanged_state, state)
        self.assertEqual(events, ())

    def test_saturated_visit_preserves_pending_history_without_persisting_ram_student(self):
        from bilqis_mlx import trainer as trainer

        school = start_new(self.course, self.init)
        prior = {"event": "PREVIOUS_PENDING_CANDIDATE", "optimizer_step": 105}
        original = {"generation": 17, "run_id": "fixture-school",
                    "school": asdict(school), "teacher": {"existing": True},
                    "_pending_visit_events": [prior]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            updated = trainer._skip_perfect_target_visit(
                path, original, school, self.course, "a.0", 12, 121)
            self.assertFalse((path / "state.json").exists())
            self.assertFalse((path / "events.jsonl").exists())
        self.assertEqual(updated["school"]["current_student"], asdict(self.init))
        self.assertEqual(updated["school"]["visits"], 1)
        self.assertEqual(updated["generation"], 18)
        self.assertEqual(updated["teacher"], original["teacher"])
        self.assertEqual(updated["_pending_visit_events"][0], prior)
        skipped = updated["_pending_visit_events"][1]
        self.assertEqual(skipped["event"], "SCHOOL_PERFECT_TARGET_VISIT_SKIPPED")
        self.assertEqual(skipped["optimizer_step"], 121)
        self.assertEqual(skipped["retained_optimizer_updates"], 0)
        self.assertEqual(skipped["target_probe_total"], 12)

    def test_weakest_three_uses_cumulative_pool_without_perfect_padding(self):
        pool = ("A.ONE", "A.TWO", "B.THREE", "C.FOUR", "C.FIVE")
        scores = {cap: Score(12, 12) for cap in pool}
        scores["A.TWO"] = Score(9, 12)
        scores["C.FIVE"] = Score(11, 12)
        self.assertEqual(weakest_three(scores, pool), ("A.TWO", "C.FIVE"))
        self.assertEqual(weakest_three({cap: Score(12,12) for cap in pool}, pool), ())

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

    def test_two_freshly_ranked_weakest_three_rounds_before_returning_to_grade_a(self):
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
        state=assess_and_settle(
            course,state,a,{f"a.{i}":(8,8) for i in range(6)})
        self.assertEqual(state.grade,"B")
        self.assertEqual(state.champions["A"],a)
        self.assertEqual(teacher_vote_weights(course,state),{a.sha256:1})
        b=cp("B",120)
        state=grade_loop(course,state,b)
        scores={**{f"a.{i}":(5,8) for i in range(6)},
                **{f"b.{i}":(8,8) for i in range(6)}}
        state=assess_and_settle(course,state,b,scores)
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
        state=assess_and_settle(
            course,state,a,{f"a.{i}":(8,8) for i in range(6)})
        b=cp("B",210)
        state=grade_loop(course,state,b)
        scores={**{f"a.{i}":(8,8) for i in range(6)},
                **{f"b.{i}":(8,8) for i in range(6)}}
        state=assess_and_settle(course,state,b,scores)
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

    def test_second_recovery_revisits_same_weakest_if_they_are_still_weak(self):
        school=grade_loop(self.course,start_new(self.course,self.init),self.init)
        scores={f"a.{i}": (1+i,8) for i in range(6)}
        school=assess(self.course,school,snapshot(self.course,self.init,scores))
        self.assertEqual(school.queue,("a.0","a.1","a.2"))
        school=grade_loop(self.course,school,self.init)
        school=assess(self.course,school,snapshot(self.course,self.init,scores))
        self.assertEqual(school.stage,"RECOVERY_2")
        self.assertEqual(school.queue,("a.0","a.1","a.2"))

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
        moved = assess_and_settle(
            course, state, student, perfect, from_rubric="c"*64)
        self.assertEqual(moved.grade, "B")

    def test_next_grade_may_use_new_cumulative_rubric_without_mutating_a(self):
        a, b = self.course.grades
        course = replace(self.course,
                         grades=(replace(a, assessment_sha256="a"*64),
                                 replace(b, assessment_sha256="b"*64)),
                         assessment_manifest_sha256="b"*64)
        student = cp("advanced", 119000)
        state = grade_loop(course, start_new(course, self.init), student)
        state = assess_and_settle(
            course, state, student, {f"a.{i}": (8,8) for i in range(6)})
        self.assertEqual(state.grade, "B")
        self.assertIsNone(state.latest_rubric_digest)
        state = grade_loop(course, state, student)
        scores = {**{f"a.{i}": (8,8) for i in range(6)},
                  **{f"b.{i}": (8,8) for i in range(6)}}
        with self.assertRaisesRegex(ValueError, "GRADE_SEALED_RUBRIC"):
            assess(course, state, snapshot(course, student, scores,
                                           from_rubric="a"*64))
        state = assess_and_settle(
            course, state, student, scores, from_rubric="b"*64)
        self.assertEqual(state.revalidation_target_grade, "B")
        self.assertEqual(state.grade, "A")
        state = grade_loop(course, state, student)
        state = assess(course, state, snapshot(course, student, scores,
                                               from_rubric="b"*64))
        state = grade_loop(course, state, student)
        state = assess(course, state, snapshot(course, student, scores,
                                               from_rubric="b"*64))
        self.assertEqual(state.stage, "WHOLE_SCHOOL_MASTERED")

    def test_backward_spiral_keeps_introduced_b_in_cumulative_assessment_pool(self):
        a, b = self.course.grades
        course = replace(
            self.course,
            grades=(replace(a, assessment_sha256="a" * 64),
                    replace(b, assessment_sha256="b" * 64)),
            assessment_manifest_sha256="b" * 64,
        )
        student = self.init
        state = grade_loop(course, start_new(course, student), student)
        state = assess_and_settle(
            course, state, student,
            {f"a.{i}": (8, 8) for i in range(6)},
            from_rubric="a" * 64)
        self.assertEqual(state.grade, "B")

        state = grade_loop(course, state, student)
        mixed = {
            **{f"a.{i}": (7 if i == 0 else 8, 8) for i in range(6)},
            **{f"b.{i}": (7, 8) for i in range(6)},
        }
        state = assess(
            course, state,
            snapshot(course, student, mixed, from_rubric="b" * 64),
        )
        self.assertEqual((state.grade, state.stage), ("A", "MAIN"))
        self.assertEqual(state.main_sweep_visited, ("B",))

        self.assertEqual(
            set(assessment_capabilities(course, state)),
            set(mixed),
        )
        state = grade_loop(course, state, student)
        state = assess(
            course, state,
            snapshot(course, student, mixed, from_rubric="b" * 64),
        )
        self.assertNotEqual(state.stage, "MAIN")

    def test_b_graduation_revalidates_a_then_b_before_starting_c(self):
        course = three_grade_course()
        a, b, reviewed = cp("A",110), cp("B",120), cp("reviewed",130)
        state = grade_loop(course, start_new(course,self.init), a)
        state = assess_and_settle(course, state, a, {
            f"a.{i}": (8,8) for i in range(6)})
        state = grade_loop(course, state, b)
        state = assess_and_settle(
            course, state, b,
            {**{f"a.{i}": (7,8) for i in range(6)},
             **{f"b.{i}": (8,8) for i in range(6)}})
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
        state = assess_and_settle(course, state, students[0], {
            f"a.{i}": (8,8) for i in range(6)})
        state = grade_loop(course, state, students[1])
        state = assess_and_settle(
            course, state, students[1],
            {**{f"a.{i}": (8,8) for i in range(6)},
             **{f"b.{i}": (8,8) for i in range(6)}})
        for grade in ("A", "B"):
            self.assertEqual(state.grade, grade)
            state = grade_loop(course, state, students[2])
            state = assess(course, state, snapshot(course, students[2],
                {**{f"a.{i}": (8,8) for i in range(6)},
                 **{f"b.{i}": (8,8) for i in range(6)}}))
        self.assertEqual(state.grade, "C")
        state = grade_loop(course, state, students[3])
        state = assess_and_settle(
            course, state, students[3], all_scores(course))
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
            state = assess_and_settle(
                course, state, model, all_scores(course, through=grade))
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
        state = assess_and_settle(
            course, state, model, {f"a.{i}": (8,8) for i in range(6)})
        state = grade_loop(course, state, model)
        state = assess_and_settle(
            course, state, model,
            {**{f"a.{i}": (8,8) for i in range(6)},
             **{f"b.{i}": (8,8) for i in range(6)}})
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
        state = assess_and_settle(
            course, state, a, {f"a.{i}": (8,8) for i in range(6)})
        state = grade_loop(course, state, b)
        state = assess_and_settle(
            course, state, b, all_scores(course, through="B"))
        with self.assertRaisesRegex(ValueError, "REVALIDATION"):
            verify_state(course, replace(state, grade_index=2))

    def test_revalidation_a_failure_uses_full_two_weakest_three_rounds(self):
        course = three_grade_course()
        student = self.init
        state = grade_loop(course, start_new(course, student), student)
        state = assess_and_settle(
            course, state, student, all_scores(course, through="A"))
        state = grade_loop(course, state, student)
        state = assess_and_settle(
            course, state, student, all_scores(course, through="B"))
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
        self.assertEqual(state.queue[:2], ("a.0", "a.1"))
        self.assertEqual(state.queue, state.first_recovery,
                         "Still-weak capabilities must remain eligible in round two")
        self.assertEqual(state.revalidation_target_grade, "B")

    def test_after_two_recovery_rounds_main_advances_to_next_imperfect_grade(self):
        course = three_grade_course()
        student = self.init
        base = start_new(course, student)
        b = course.grades[1]
        state = replace(
            base,
            grade_index=1,
            introduction_stage=(len(b.teaching_stages) - 1 if b.teaching_stages else 0),
            stage="ASSESS_RECOVERY_2",
            queue=(),
            first_recovery=("b.0",),
            champions={grade: student for grade in ("A", "B", "C")},
            revalidation_target_grade="C",
        )
        verify_state(course, state)
        imperfect = all_scores(course, imperfect=("a.0", "b.0", "c.0"))

        moved = assess(course, state, snapshot(course, student, imperfect))

        self.assertEqual(moved.stage, "MAIN")
        self.assertEqual(moved.grade, "C")
        self.assertEqual(
            moved.queue,
            tuple(cap.id for cap in course.grades[2].capabilities),
            "After the second weakest-three round, the next imperfect grade gets a full ordinary pass",
        )

    def test_after_two_recovery_rounds_skips_perfect_grades_and_wraps(self):
        course = three_grade_course()
        student = self.init
        base = start_new(course, student)
        b = course.grades[1]
        state = replace(
            base,
            grade_index=1,
            introduction_stage=(len(b.teaching_stages) - 1 if b.teaching_stages else 0),
            stage="ASSESS_RECOVERY_2",
            queue=(),
            first_recovery=("b.0",),
            champions={grade: student for grade in ("A", "B", "C")},
            revalidation_target_grade="C",
        )
        verify_state(course, state)
        imperfect = all_scores(course, imperfect=("a.0", "b.0"))

        moved = assess(course, state, snapshot(course, student, imperfect))

        self.assertEqual(moved.stage, "MAIN")
        self.assertEqual(moved.grade, "A")
        self.assertEqual(
            moved.queue,
            tuple(cap.id for cap in course.grades[0].capabilities),
        )

    def test_admitted_grade_rejects_fabricated_one_question_perfect_score(self):
        grade = replace(self.course.grades[0],
                        exam_item_counts=tuple((f"a.{i}", 12) for i in range(6)))
        course = replace(self.course, grades=(grade, self.course.grades[1]))
        state = grade_loop(course, start_new(course, self.init), self.init)
        with self.assertRaisesRegex(ValueError, "SEALED_ITEM_COUNT"):
            assess(course, state, snapshot(
                course, self.init, {f"a.{i}": (1,1) for i in range(6)}))
        moved = assess_and_settle(
            course, state, self.init, {f"a.{i}": (12,12) for i in range(6)})
        self.assertEqual(moved.grade, "B")

    def test_partial_grade_a_waits_and_future_grade_appends_without_relearning(self):
        full = self.course
        a = replace(full.grades[0], assessment_sha256="a"*64)
        a_only = replace(full, grades=(a,), version="partial-A/v1",
                         program_complete=False, assessment_manifest_sha256="a"*64)
        student = cp("human-A", 116800)
        state = grade_loop(a_only, start_new(a_only, self.init), student)
        state = assess_and_settle(
            a_only, state, student, {f"a.{i}": (12,12) for i in range(6)})
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
            with self.assertRaisesRegex(ValueError, "SCHOOL.STATE.COURSE_DIGEST_MISMATCH"):
                read_state(target, successor)
        resumed = append_next_grade(a_only, successor, state)
        self.assertEqual(resumed.grade, "B")
        self.assertEqual(resumed.queue, tuple(f"b.{i}" for i in range(6)))
        self.assertEqual(resumed.champions["A"], student)
        self.assertEqual(resumed.current_student, student)
        self.assertEqual(resumed.latest_rubric_digest, None)
        with self.assertRaisesRegex(ValueError, "SCHOOL.STATE.COURSE_DIGEST_MISMATCH"):
            append_next_grade(a_only, successor, resumed)
        with self.assertRaisesRegex(ValueError, "CHANGE_PREVIOUS_GRADE"):
            changed_a = replace(a, assessment_sha256="c"*64)
            append_next_grade(a_only, replace(successor, grades=(changed_a, full.grades[1])),
                              state)

    def test_explicit_debt_admission_adds_next_grade_without_fabricating_prior_champion(self):
        from bilqis_mlx.curriculum import scheduler

        full = sealed_three_grade_course()
        previous = replace(
            full, grades=full.grades[:2], version="synthetic/ab-debt-v1",
            program_complete=False)
        successor = replace(full, version="synthetic/abc-debt-v1",
                            program_complete=False)
        student = cp("debt-candidate", 900)
        state = start_new(previous, student)
        state = replace(
            state, grade_index=1, stage="RECOVERY_2", queue=("b.0",),
            first_recovery=("b.0",), champions={"A": student},
            latest_rubric_digest=previous.grades[-1].assessment_sha256)

        migrated = scheduler.append_next_grade_with_debt(
            previous, successor, state, ("a.0", "b.0"))

        self.assertEqual(migrated.grade, "C")
        self.assertEqual(migrated.carried_mastery_debt, ("a.0", "b.0"))
        self.assertEqual(set(migrated.champions), {"A"})
        self.assertNotIn("B", migrated.champions)
        self.assertIn("b.0", assessment_capabilities(successor, migrated))

    def test_debt_admitted_school_spirals_until_one_checkpoint_clears_all_active_debt(self):
        from bilqis_mlx.curriculum import scheduler

        full = sealed_three_grade_course()
        previous = replace(
            full, grades=full.grades[:2], version="synthetic/ab-debt-v2",
            program_complete=False)
        successor = replace(full, version="synthetic/abc-debt-v2",
                            program_complete=False)
        student = cp("debt-spiral", 901)
        state = start_new(previous, student)
        state = replace(
            state, grade_index=1, stage="RECOVERY_2", queue=("b.0",),
            first_recovery=("b.0",), champions={"A": student},
            latest_rubric_digest=previous.grades[-1].assessment_sha256)
        state = scheduler.append_next_grade_with_debt(
            previous, successor, state, ("b.0",))

        state = grade_loop(successor, state, student)
        state = assess_and_settle(
            successor, state, student,
            all_scores(successor, imperfect=("b.0",)),
            from_rubric=successor.grades[-1].assessment_sha256)
        self.assertEqual((state.grade, state.stage), ("B", "MAIN"))
        self.assertEqual(state.carried_mastery_debt, ("b.0",))
        self.assertIn("C", state.champions)
        self.assertNotIn("B", state.champions)

        state = grade_loop(successor, state, student)
        state = assess_and_settle(
            successor, state, student, all_scores(successor),
            from_rubric=successor.grades[-1].assessment_sha256)
        self.assertEqual(state.stage, "AWAITING_NEXT_GRADE")
        self.assertEqual(state.grade, "C")
        self.assertEqual(state.carried_mastery_debt, ())
        self.assertEqual(set(state.champions), {"A", "B", "C"})


if __name__=="__main__":
    unittest.main()

class WholeStudentSelectionTests(unittest.TestCase):
    def test_best_complete_candidate_by_same_full_rubric_not_latest_step(self):
        course=sample_course()
        older=cp("older",100)
        newer=cp("newer",10000)
        pool={**{f"a.{i}":(8,8) for i in range(6)},
              **{f"b.{i}":(7,8) for i in range(6)}}
        from bilqis_mlx.curriculum.scheduler import choose_best_whole_student
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
        from bilqis_mlx.curriculum.scheduler import choose_best_whole_student
        with self.assertRaisesRegex(ValueError,"NOT_COMPARABLE"):
            choose_best_whole_student(course,
               ((a,snapshot(course,a,pool)),
                (b,snapshot(course,b,pool,from_rubric="b"*64))), ("A",))
