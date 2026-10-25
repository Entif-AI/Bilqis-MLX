"""A staged grade teaches and assesses constituents before dependent concepts."""
from dataclasses import asdict, replace
import hashlib
import json
import unittest

from bilqis_mlx.curriculum import ExamItem, validate, validate_exam_item
from bilqis_mlx.curriculum.scheduler import (
    _at_introduction_stage, _enter_grade, assess, assess_withheld,
    assessment_capabilities, next_capability, start_new, visit,
)
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


def finish_promotion_sweep(course, state, pointer, scores):
    while state.stage == "PROMOTION_SWEEP":
        state = visit(course, state, next_capability(state), pointer)
        state = assess(course, state, snapshot(course, pointer, scores))
    return state


def enter_c(course):
    pointer = cp("whole-student")
    state = start_new(course, pointer)
    # A, initial B, then the required A->B replay, all at one complete student.
    for grade in ("A", "B", "A", "B"):
        assert state.grade == grade
        state = grade_loop(course, state, pointer)
        scores = all_scores(
            course, through=grade if grade == "A" and not state.champions else "B")
        state = assess(course, state, snapshot(course, pointer, scores))
        state = finish_promotion_sweep(course, state, pointer, scores)
    return state, pointer


class StagedSchoolTests(unittest.TestCase):
    def test_c_frontier_due_b_turn_is_full_imperfect_grade_pass(self):
        course = staged_course()
        state, pointer = enter_c(course)
        last_stage = len(course.grades[-1].teaching_stages) - 1
        state = _at_introduction_stage(
            state, last_stage, stage="MAIN",
            queue=course.grades[-1].teaching_stages[last_stage])
        introduced_c = tuple(
            capability
            for stage in course.grades[-1].teaching_stages
            for capability in stage)
        state = replace(
            state,
            champions={"A": state.champions["A"]},
            carried_mastery_debt=("b.0", "b.1", *introduced_c),
            main_sweep_visited=(),
        )
        scores = {
            capability: (8, 8)
            for capability in assessment_capabilities(course, state)
        }
        for capability in ("b.0", "b.1", *introduced_c):
            scores[capability] = (4, 8)

        for _ in range(20):
            capability = next_capability(state)
            self.assertIsNotNone(capability)
            if capability.startswith("b."):
                break
            state = visit(course, state, capability, pointer)
            if state.stage.startswith("ASSESS_"):
                state = assess(
                    course, state, snapshot(course, pointer, scores))
        else:
            self.fail("B never received its bounded training turn")

        self.assertEqual(state.grade, "B")
        self.assertEqual(state.stage, "MAIN")
        self.assertEqual(state.queue, ("b.0", "b.1"))

    def test_c_frontier_b_full_run_yields_four_non_b_turns_before_repeating(self):
        course = staged_course()
        state, pointer = enter_c(course)
        last_stage = len(course.grades[-1].teaching_stages) - 1
        state = _at_introduction_stage(
            state, last_stage, stage="MAIN",
            queue=course.grades[-1].teaching_stages[last_stage])
        introduced_c = tuple(
            capability
            for stage in course.grades[-1].teaching_stages
            for capability in stage)
        state = replace(
            state,
            champions={"A": state.champions["A"]},
            carried_mastery_debt=("b.0", "b.1", *introduced_c),
            main_sweep_visited=(),
        )
        scores = {
            capability: (8, 8)
            for capability in assessment_capabilities(course, state)
        }
        for capability in ("b.0", "b.1", *introduced_c):
            scores[capability] = (4, 8)

        # Start at the first due B turn, then prove the complete B pass resets
        # the cadence and cannot recur until four non-B training queues finish.
        state = replace(state, non_b_training_turns_since_b_run=4)
        state = grade_loop(course, state, pointer)
        state = assess(course, state, snapshot(course, pointer, scores))
        self.assertEqual((state.grade, state.queue), ("B", ("b.0", "b.1")))

        while state.grade == "B":
            state = visit(course, state, next_capability(state), pointer)
            if state.stage.startswith("ASSESS_"):
                state = assess(
                    course, state, snapshot(course, pointer, scores))
        self.assertEqual(state.non_b_training_turns_since_b_run, 0)

        completed_non_b_turns = 0
        while completed_non_b_turns < 4:
            self.assertNotEqual(state.grade, "B")
            while not state.stage.startswith("ASSESS_"):
                state = visit(course, state, next_capability(state), pointer)
            completed_non_b_turns += 1
            state = assess(course, state, snapshot(course, pointer, scores))
            if completed_non_b_turns < 4:
                self.assertNotEqual(state.grade, "B")

        self.assertEqual(completed_non_b_turns, 4)
        self.assertEqual((state.grade, state.queue), ("B", ("b.0", "b.1")))

    def test_due_b_run_follows_promotion_stage_advance_without_blocking_advance(self):
        course = staged_course()
        state, pointer = enter_c(course)
        state = _at_introduction_stage(state, 1, stage="MAIN", queue=("c.1",))
        state = replace(
            state,
            champions={"A": state.champions["A"]},
            carried_mastery_debt=("b.0", "b.1", "c.0", "c.1"),
            non_b_training_turns_since_b_run=3,
        )
        scores = {
            capability: (8, 8)
            for capability in assessment_capabilities(course, state)
        }
        scores["b.0"] = (4, 8)
        scores["b.1"] = (4, 8)
        scores["c.0"] = (8, 8)
        scores["c.1"] = (8, 8)

        state = visit(course, state, "c.1", pointer)
        state = assess(course, state, snapshot(course, pointer, scores))
        self.assertEqual(state.stage, "PROMOTION_SWEEP")
        state = finish_promotion_sweep(course, state, pointer, scores)

        self.assertEqual((state.grade, state.stage), ("B", "MAIN"))
        self.assertEqual(state.queue, ("b.0", "b.1"))
        self.assertEqual(dict(state.introduction_frontiers)["C"], 2)

    def test_legacy_b_queue_reanchors_to_saved_c_frontier_on_resume(self):
        course = staged_course()
        state, pointer = enter_c(course)
        last_stage = len(course.grades[-1].teaching_stages) - 1
        state = _at_introduction_stage(
            state, last_stage, stage="MAIN",
            queue=course.grades[-1].teaching_stages[last_stage])
        state = replace(
            state,
            champions={"A": state.champions["A"]},
            carried_mastery_debt=("b.0", "b.1", f"c.{last_stage}"),
        )
        state = _enter_grade(
            course, state, 1, stage="MAIN", first_recovery=(),
            main_sweep_visited=())
        payload = asdict(state)
        payload.pop("frontier_priority_visits")
        payload.pop("nongating_b_visits")

        restored = _state_from_json(payload, course)

        self.assertEqual(restored.grade, "C")
        self.assertEqual(restored.stage, "MAIN")
        self.assertEqual(restored.queue, (f"c.{last_stage}",))
        self.assertEqual(restored.frontier_priority_visits, 0)
        self.assertEqual(restored.nongating_b_visits, 0)

    def test_pre_adr094_receipt_migrates_with_one_full_b_run_due(self):
        course = staged_course()
        state, pointer = enter_c(course)
        last_stage = len(course.grades[-1].teaching_stages) - 1
        state = _at_introduction_stage(
            state, last_stage, stage="RECOVERY_1",
            queue=(f"c.{last_stage}", "b.0"))
        state = replace(
            state,
            champions={"A": state.champions["A"]},
            carried_mastery_debt=("b.0", "b.1", f"c.{last_stage}"),
            frontier_priority_visits=44,
            nongating_b_visits=11,
        )
        payload = asdict(state)
        payload.pop("non_b_training_turns_since_b_run")

        restored = _state_from_json(payload, course)

        self.assertEqual((restored.grade, restored.stage), ("C", "MAIN"))
        self.assertEqual(restored.queue, (f"c.{last_stage}",))
        self.assertEqual(restored.non_b_training_turns_since_b_run, 4)
        self.assertEqual((restored.frontier_priority_visits,
                          restored.nongating_b_visits), (44, 11))

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
    def test_unfinished_b_debt_does_not_take_over_incomplete_or_final_c_stages(self):
        course = staged_course()
        for stage in (0, len(course.grades[-1].teaching_stages) - 1):
            with self.subTest(c_stage=stage):
                state, pointer = enter_c(course)
                current = f"c.{stage}"
                state = _at_introduction_stage(
                    state, stage, queue=(current,))
                state = replace(
                    state, champions={"A": state.champions["A"]},
                    carried_mastery_debt=("b.0", "b.1", current))
                scores = {
                    cap: (8, 8)
                    for cap in assessment_capabilities(course, state)
                }
                scores["b.0"] = (4, 8)
                scores["b.1"] = (4, 8)
                scores[current] = (0, 8)

                state = grade_loop(course, state, pointer)
                state = assess(
                    course, state, snapshot(course, pointer, scores))
                self.assertEqual((state.grade, state.stage), ("C", "RECOVERY_1"))
                self.assertNotIn("b.0", state.queue)
                self.assertNotIn("b.1", state.queue)
                self.assertIn(current, state.queue)
                if stage == 0:
                    self.assertNotIn(
                        "c.1", assessment_capabilities(course, state))
                self.assertEqual(
                    dict(state.introduction_frontiers)["C"], stage)

                self.assertIn("b.0", state.carried_mastery_debt)
                self.assertIn("b.1", state.carried_mastery_debt)

    def test_c_withheld_allows_b_full_run_after_four_non_b_turns(self):
        course = staged_course()
        state, pointer = enter_c(course)
        last_stage = len(course.grades[-1].teaching_stages) - 1
        state = _at_introduction_stage(
            state, last_stage, stage="ASSESS_RECOVERY_2", queue=(),
            first_recovery=("b.0", f"c.{last_stage}"))
        state = replace(
            state, champions={"A": state.champions["A"]},
            carried_mastery_debt=("b.0", f"c.{last_stage}"))
        withheld = (f"c.{last_stage}",)
        scores = {
            capability: (8, 8)
            for capability in assessment_capabilities(course, state)
            if capability not in withheld
        }
        scores["b.0"] = (4, 8)

        resumed = assess_withheld(
            course, state, snapshot(course, pointer, scores), withheld)

        self.assertEqual(resumed.stage, "DEFERRED_STAGNATION")
        self.assertNotIn("b.0", resumed.queue)
        self.assertIn(f"c.{last_stage}", resumed.carried_mastery_debt)
        self.assertEqual(
            dict(resumed.introduction_frontiers)["C"], last_stage)

        budgeted = replace(state, non_b_training_turns_since_b_run=4)
        resumed = assess_withheld(
            course, budgeted, snapshot(course, pointer, scores), withheld)
        self.assertEqual((resumed.grade, resumed.stage), ("B", "MAIN"))
        self.assertEqual(resumed.queue, ("b.0",))

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
        scores = {c: (8, 8) for c in assessment_capabilities(course, state)}
        scores["c.0"] = (7, 8)
        state = assess(course, state, snapshot(course, pointer, scores))
        self.assertEqual(state.introduction_stage, 0)
        self.assertEqual(state.grade_exam_epoch, epoch)
        state = grade_loop(course, state, pointer)
        scores = {c: (8, 8) for c in assessment_capabilities(course, state)}
        state = assess(course, state, snapshot(course, pointer, scores))
        state = finish_promotion_sweep(course, state, pointer, scores)
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

    def test_grade_mean_promotion_sweep_allows_one_semantic_below_ninety(self):
        course = staged_course()
        state, pointer = enter_c(course)
        state = grade_loop(course, state, pointer)
        perfect = {c: (8, 8) for c in assessment_capabilities(course, state)}
        state = assess(course, state, snapshot(course, pointer, perfect))
        state = finish_promotion_sweep(course, state, pointer, perfect)
        self.assertEqual(state.introduction_stage, 1)

        state = grade_loop(course, state, pointer)
        scores = {c: (8, 8) for c in assessment_capabilities(course, state)}
        scores["c.1"] = (17, 20)
        state = assess(course, state, snapshot(course, pointer, scores))
        self.assertEqual(state.stage, "PROMOTION_SWEEP")
        self.assertEqual(state.queue, ("c.0", "c.1"))

        state = visit(course, state, "c.0", pointer)
        state = assess(course, state, snapshot(course, pointer, scores))
        self.assertEqual(state.stage, "PROMOTION_SWEEP")
        self.assertEqual(state.queue, ("c.1",))

        state = visit(course, state, "c.1", pointer)
        exactly_ninety = dict(scores)
        exactly_ninety["c.1"] = (16, 20)
        state = assess(course, state, snapshot(course, pointer, exactly_ninety))
        self.assertEqual(state.introduction_stage, 2)
        self.assertEqual(state.queue, ("c.2",))
        self.assertIn("c.1", state.carried_mastery_debt)
        self.assertNotIn("C", state.champions)

    def test_exactly_ninety_mean_starts_promotion_sweep(self):
        course = staged_course()
        state, pointer = enter_c(course)
        state = grade_loop(course, state, pointer)
        perfect = {c: (8, 8) for c in assessment_capabilities(course, state)}
        state = assess(course, state, snapshot(course, pointer, perfect))
        state = finish_promotion_sweep(course, state, pointer, perfect)
        state = grade_loop(course, state, pointer)
        exactly_ninety = {
            c: (8, 8) for c in assessment_capabilities(course, state)
        }
        exactly_ninety["c.1"] = (16, 20)

        state = assess(
            course, state, snapshot(course, pointer, exactly_ninety))

        self.assertEqual(state.stage, "PROMOTION_SWEEP")
        self.assertEqual(state.queue, ("c.0", "c.1"))
        self.assertEqual(state.introduction_stage, 1)
        self.assertNotIn("c.2", assessment_capabilities(course, state))

    def test_grade_mean_promotion_sweep_aborts_only_when_mean_falls_below_ninety(self):
        course = staged_course()
        state, pointer = enter_c(course)
        state = grade_loop(course, state, pointer)
        perfect = {c: (8, 8) for c in assessment_capabilities(course, state)}
        state = assess(course, state, snapshot(course, pointer, perfect))
        state = finish_promotion_sweep(course, state, pointer, perfect)
        state = grade_loop(course, state, pointer)
        scores = {c: (8, 8) for c in assessment_capabilities(course, state)}
        scores["c.1"] = (17, 20)
        state = assess(course, state, snapshot(course, pointer, scores))

        state = visit(course, state, "c.0", pointer)
        state = assess(course, state, snapshot(course, pointer, scores))
        state = visit(course, state, "c.1", pointer)
        below_ninety = dict(scores)
        below_ninety["c.1"] = (15, 20)
        state = assess(course, state, snapshot(course, pointer, below_ninety))

        self.assertEqual(state.introduction_stage, 1)
        self.assertNotEqual(state.stage, "PROMOTION_SWEEP")
        self.assertNotEqual(state.stage, "ASSESS_PROMOTION_SWEEP")
        self.assertNotIn("c.2", assessment_capabilities(course, state))

    def test_promotion_sweep_only_replaces_the_semantic_just_rescored(self):
        course = staged_course()
        state, pointer = enter_c(course)
        state = grade_loop(course, state, pointer)
        perfect = {c: (8, 8) for c in assessment_capabilities(course, state)}
        state = assess(course, state, snapshot(course, pointer, perfect))
        state = finish_promotion_sweep(course, state, pointer, perfect)
        state = grade_loop(course, state, pointer)
        baseline = {c: (8, 8) for c in assessment_capabilities(course, state)}
        baseline["c.1"] = (17, 20)
        state = assess(course, state, snapshot(course, pointer, baseline))
        self.assertEqual(state.queue, ("c.0", "c.1"))

        state = visit(course, state, "c.0", pointer)
        fresh_regression_elsewhere = dict(baseline)
        fresh_regression_elsewhere["c.1"] = (15, 20)
        state = assess(
            course, state,
            snapshot(course, pointer, fresh_regression_elsewhere))

        self.assertEqual(state.stage, "PROMOTION_SWEEP")
        self.assertEqual(state.queue, ("c.1",))
        self.assertEqual(state.introduction_stage, 1)

    def test_promotion_sweep_state_round_trips_through_runtime_receipt(self):
        course = staged_course()
        state, pointer = enter_c(course)
        state = grade_loop(course, state, pointer)
        perfect = {c: (8, 8) for c in assessment_capabilities(course, state)}
        state = assess(course, state, snapshot(course, pointer, perfect))
        state = finish_promotion_sweep(course, state, pointer, perfect)
        state = grade_loop(course, state, pointer)
        scores = {c: (8, 8) for c in assessment_capabilities(course, state)}
        scores["c.1"] = (17, 20)
        state = assess(course, state, snapshot(course, pointer, scores))

        restored = _state_from_json(
            json.loads(json.dumps(asdict(state))), course)

        self.assertEqual(restored, state)
        self.assertEqual(restored.stage, "PROMOTION_SWEEP")
        self.assertEqual(restored.queue, ("c.0", "c.1"))

    def test_incomplete_staged_grade_restores_frontier_after_cross_grade_spiral(self):
        course = staged_course()
        state, pointer = enter_c(course)
        state = replace(state, introduction_stage=3, stage="MAIN", queue=("c.3",))

        elsewhere = _enter_grade(course, state, 0, stage="MAIN", first_recovery=())
        returned = _enter_grade(course, elsewhere, 2, stage="MAIN", first_recovery=())

        self.assertEqual(returned.grade, "C")
        self.assertEqual(returned.introduction_stage, 3)
        self.assertEqual(returned.queue, ("c.3",))
        self.assertNotIn("c.4", assessment_capabilities(course, returned))

    def test_full_c_pass_runs_a_b_c_replay_without_reintroducing_stages(self):
        course = staged_course()
        state, pointer = enter_c(course)
        for stage in range(6):
            state = grade_loop(course, state, pointer)
            scores = {c: (8, 8) for c in assessment_capabilities(course, state)}
            state = assess(course, state, snapshot(course, pointer, scores))
            state = finish_promotion_sweep(course, state, pointer, scores)
            if stage < 5:
                self.assertEqual(state.introduction_stage, stage+1)
        self.assertEqual(state.grade, "A")
        self.assertEqual(state.revalidation_target_grade, "C")
        for grade in ("A", "B"):
            state = grade_loop(course, state, pointer)
            scores = {c: (8, 8) for c in assessment_capabilities(course, state)}
            state = assess(course, state, snapshot(course, pointer, scores))
            state = finish_promotion_sweep(course, state, pointer, scores)
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

class DebtPromotionPartialAssessmentRegression(unittest.TestCase):
    def test_perfect_revisited_b_keeps_debt_and_returns_to_unfinished_c(self):
        course = staged_course()
        student = cp('partial-debt-success')
        state, _ = enter_c(course)
        state = _enter_grade(course, state, 1, stage='ASSESS_MAIN',
                             first_recovery=(),
                             carried_mastery_debt=('a.0', 'b.0'),
                             latest_rubric_digest=None)
        state = replace(state, queue=(), current_student=student)
        scores = {cap: (8, 8) for cap in assessment_capabilities(course, state)}
        self.assertNotIn('c.1', scores)
        next_state = assess(course, state, snapshot(course, student, scores))
        self.assertEqual((next_state.grade, next_state.stage), ('C', 'MAIN'))
        self.assertEqual(next_state.introduction_stage, 0)
        self.assertEqual(next_state.carried_mastery_debt, ('a.0', 'b.0'))
        self.assertNotEqual(next_state.stage, 'AWAITING_NEXT_GRADE')
