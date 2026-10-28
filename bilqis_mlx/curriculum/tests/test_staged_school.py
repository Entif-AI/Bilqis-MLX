"""A staged grade teaches and assesses constituents before dependent concepts."""
from dataclasses import asdict, replace
import hashlib
import json
import unittest

from bilqis_mlx.curriculum import ExamItem, validate, validate_exam_item
from bilqis_mlx.curriculum.scheduler import (
    DebtCadencePolicy, _at_introduction_stage, _debt_run_due,
    _debt_run_queue, _enter_grade, _enter_mature_debt_repair,
    _continue_main_sweep, _frontier_recovery_queue, assess,
    _mature_debt_repair_grade,
    assess_withheld, assessment_capabilities, next_capability, start_new,
    visit, Score,
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
    state = start_new(
        course, pointer,
        debt_cadence_policy=DebtCadencePolicy.from_legacy_adr094())
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
    def test_mature_grade_debt_tracks_fixed_frontier_net_loss_and_repair(self):
        course = staged_course()
        state, pointer = enter_c(course)
        state = replace(state, grade_index=1, stage="MAIN", queue=("b.0",))
        lost = {"status": "MEASURED", "grades": {
            "A": {"before": 48, "after": 46, "net_correct_delta": -2}}}

        state = visit(
            course, state, "b.0", pointer, retention_frontier=lost)
        self.assertEqual(state.mature_grade_debt, (("A", 2),))
        self.assertEqual(_mature_debt_repair_grade(course, state), "A")

        state = replace(state, grade_index=0, stage="MAIN", queue=("a.0",))
        repaired = {"status": "MEASURED", "grades": {
            "A": {"before": 46, "after": 47, "net_correct_delta": 1}}}
        state = visit(
            course, state, "a.0", pointer, retention_frontier=repaired)
        self.assertEqual(state.mature_grade_debt, (("A", 1),))
        self.assertIsNone(_mature_debt_repair_grade(course, state))

    def test_mature_debt_repair_is_one_full_grade_pass_per_school_sweep(self):
        course = staged_course()
        state, _ = enter_c(course)
        state = replace(
            state, mature_grade_debt=(("A", 2),),
            main_sweep_visited=(),
        )

        repair = _enter_mature_debt_repair(course, state, reset_sweep=False)

        self.assertEqual(repair.grade, "A")
        self.assertEqual(
            repair.queue,
            tuple(cap.id for cap in course.grades[0].capabilities),
        )
        completed = replace(repair, main_sweep_visited=("A",))
        self.assertIsNone(
            _enter_mature_debt_repair(course, completed, reset_sweep=False))

    def test_completed_mature_repair_pass_yields_to_next_imperfect_grade(self):
        course = staged_course()
        state, pointer = enter_c(course)
        state = replace(
            state, grade_index=0, stage="ASSESS_MAIN", queue=(),
            main_sweep_visited=(), mature_grade_debt=(("A", 2),),
        )
        scores = all_scores(course, imperfect=("a.0", "b.0", "c.0"))

        continued = _continue_main_sweep(
            course, state, snapshot(course, pointer, scores))

        self.assertEqual(continued.grade, "B")
        self.assertEqual(continued.main_sweep_visited, ("A",))

    def test_progression_frontier_keeps_bounded_priority_until_mastered(self):
        course = staged_course()
        state, pointer = enter_c(course)
        state = replace(
            state, grade_index=2, stage="ASSESS_MAIN", queue=(),
            main_sweep_visited=("A", "B"), frontier_catchup_passes=0,
        )
        scores = all_scores(course, through="C")
        # Ten introduced A/B semantics sit well above the one introduced C
        # semantic. The 10:1 shape should grant four total C passes this sweep,
        # yielding roughly 29% C visits instead of capability-count fairness.
        for capability in scores:
            scores[capability] = (7, 8)
        scores["c.0"] = (3, 8)
        snap = snapshot(course, pointer, scores)

        for completed in range(1, 4):
            state = _continue_main_sweep(course, state, snap)
            self.assertEqual(state.grade, "C")
            self.assertEqual(state.frontier_catchup_passes, completed)
            self.assertNotIn("C", state.main_sweep_visited)
            state = replace(state, stage="ASSESS_MAIN", queue=())

        continued = _continue_main_sweep(course, state, snap)
        self.assertIsNone(continued)

        caught_up = dict(scores)
        caught_up["c.0"] = (7, 8)
        state = replace(state, frontier_catchup_passes=0,
                        main_sweep_visited=("A", "B"))
        continued = _continue_main_sweep(
            course, state, snapshot(course, pointer, caught_up))
        self.assertEqual((continued.grade, continued.frontier_catchup_passes),
                         ("C", 1))

        mastered = dict(caught_up)
        mastered["c.0"] = (8, 8)
        self.assertIsNone(_continue_main_sweep(
            course, state, snapshot(course, pointer, mastered)))

    def test_debt_roles_and_cadence_come_from_policy_data(self):
        course = staged_course()
        state, pointer = enter_c(course)
        policy = DebtCadencePolicy(
            bounded_debt_grade_id="A",
            progression_priority_grade_id="C",
            non_debt_turns_per_run=2)
        state = replace(state, debt_cadence_policy=policy,
                        carried_mastery_debt=("a.0", "c.0"),
                        non_b_training_turns_since_b_run=1)
        scores = snapshot(course, pointer, all_scores(course, through="C")).scores
        scores["a.0"] = Score(4, 8)
        scores["c.0"] = Score(4, 8)

        self.assertFalse(_debt_run_due(course, state))
        state = replace(state, non_b_training_turns_since_b_run=2)
        self.assertTrue(_debt_run_due(course, state))
        self.assertEqual(_debt_run_queue(course, state, scores), ("a.0",))
        self.assertEqual(
            _frontier_recovery_queue(course, state, scores, ("a.0", "c.0")),
            ("c.0",))

    def test_new_state_does_not_infer_historical_debt_cadence(self):
        state = start_new(staged_course(), cp("new-school"))
        self.assertIsNone(state.debt_cadence_policy)

    def test_legacy_school_state_translates_adr094_cadence_without_rewriting_input(self):
        course = staged_course()
        state, _ = enter_c(course)
        legacy = asdict(state)
        legacy.pop("debt_cadence_policy")

        migrated = _state_from_json(legacy, course)

        self.assertNotIn("debt_cadence_policy", legacy)
        self.assertEqual(migrated.debt_cadence_policy,
                         DebtCadencePolicy.from_legacy_adr094())

    def test_explicit_null_c_frontier_policy_rehydrates_adr094_cadence(self):
        course = staged_course()
        state, _ = enter_c(course)
        payload = asdict(state)
        payload["debt_cadence_policy"] = None

        restored = _state_from_json(payload, course)

        self.assertEqual(restored.debt_cadence_policy,
                         DebtCadencePolicy.from_legacy_adr094())

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

    def test_promotion_sweep_requires_ninety_two_percent_entry_mean(self):
        course = staged_course()
        state, pointer = enter_c(course)
        state = grade_loop(course, state, pointer)
        perfect = {c: (8, 8) for c in assessment_capabilities(course, state)}
        state = assess(course, state, snapshot(course, pointer, perfect))
        state = finish_promotion_sweep(course, state, pointer, perfect)
        state = grade_loop(course, state, pointer)
        below_entry = {
            c: (8, 8) for c in assessment_capabilities(course, state)
        }
        below_entry["c.1"] = (419, 500)  # (100% + 83.8%) / 2 = 91.9%

        state = assess(
            course, state, snapshot(course, pointer, below_entry))

        self.assertNotEqual(state.stage, "PROMOTION_SWEEP")
        self.assertEqual(state.introduction_stage, 1)
        state, pointer = enter_c(course)
        state = grade_loop(course, state, pointer)
        perfect = {c: (8, 8) for c in assessment_capabilities(course, state)}
        state = assess(course, state, snapshot(course, pointer, perfect))
        state = finish_promotion_sweep(course, state, pointer, perfect)
        state = grade_loop(course, state, pointer)
        exactly_entry = {
            c: (8, 8) for c in assessment_capabilities(course, state)
        }
        exactly_entry["c.1"] = (21, 25)  # (100% + 84%) / 2 = 92%

        state = assess(
            course, state, snapshot(course, pointer, exactly_entry))

        self.assertEqual(state.stage, "PROMOTION_SWEEP")
        self.assertEqual(state.queue, ("c.0", "c.1"))
        self.assertEqual(state.introduction_stage, 1)
        self.assertNotIn("c.2", assessment_capabilities(course, state))

    def test_promotion_sweep_hysteresis_aborts_only_below_eighty_seven_percent(self):
        course = staged_course()
        state, pointer = enter_c(course)
        state = grade_loop(course, state, pointer)
        perfect = {c: (8, 8) for c in assessment_capabilities(course, state)}
        state = assess(course, state, snapshot(course, pointer, perfect))
        state = finish_promotion_sweep(course, state, pointer, perfect)
        state = grade_loop(course, state, pointer)
        scores = {c: (8, 8) for c in assessment_capabilities(course, state)}
        scores["c.1"] = (21, 25)
        state = assess(course, state, snapshot(course, pointer, scores))

        state = visit(course, state, "c.0", pointer)
        state = assess(course, state, snapshot(course, pointer, scores))
        state = visit(course, state, "c.1", pointer)
        exactly_exit = dict(scores)
        exactly_exit["c.1"] = (37, 50)  # (100% + 74%) / 2 = 87%
        state = assess(course, state, snapshot(course, pointer, exactly_exit))

        self.assertEqual(state.introduction_stage, 2)
        self.assertEqual(state.queue, ("c.2",))

        state, pointer = enter_c(course)
        state = grade_loop(course, state, pointer)
        perfect = {c: (8, 8) for c in assessment_capabilities(course, state)}
        state = assess(course, state, snapshot(course, pointer, perfect))
        state = finish_promotion_sweep(course, state, pointer, perfect)
        state = grade_loop(course, state, pointer)
        scores = {c: (8, 8) for c in assessment_capabilities(course, state)}
        scores["c.1"] = (21, 25)
        state = assess(course, state, snapshot(course, pointer, scores))

        state = visit(course, state, "c.0", pointer)
        state = assess(course, state, snapshot(course, pointer, scores))
        state = visit(course, state, "c.1", pointer)
        below_exit = dict(scores)
        below_exit["c.1"] = (369, 500)  # (100% + 73.8%) / 2 = 86.9%
        state = assess(course, state, snapshot(course, pointer, below_exit))

        self.assertEqual(state.introduction_stage, 1)
        self.assertNotEqual(state.stage, "PROMOTION_SWEEP")
        self.assertNotEqual(state.stage, "ASSESS_PROMOTION_SWEEP")
        self.assertNotIn("c.2", assessment_capabilities(course, state))

    def test_failed_promotion_sweep_does_not_retrigger_on_same_student_flux(self):
        course = staged_course()
        state, pointer = enter_c(course)
        state = grade_loop(course, state, pointer)
        perfect = {c: (8, 8) for c in assessment_capabilities(course, state)}
        state = assess(course, state, snapshot(course, pointer, perfect))
        state = finish_promotion_sweep(course, state, pointer, perfect)
        state = grade_loop(course, state, pointer)

        qualifying = {c: (8, 8) for c in assessment_capabilities(course, state)}
        qualifying["c.1"] = (21, 25)
        state = assess(course, state, snapshot(course, pointer, qualifying))
        self.assertEqual(state.stage, "PROMOTION_SWEEP")

        state = visit(course, state, "c.0", pointer)
        state = assess(course, state, snapshot(course, pointer, qualifying))
        state = visit(course, state, "c.1", pointer)
        below_floor = dict(qualifying)
        below_floor["c.1"] = (7, 10)
        state = assess(course, state, snapshot(course, pointer, below_floor))
        self.assertEqual(state.stage, "RECOVERY_1")

        state = grade_loop(course, state, pointer)
        reranked = {c: (8, 8) for c in assessment_capabilities(course, state)}
        reranked["c.1"] = (21, 25)
        state = assess(course, state, snapshot(course, pointer, reranked))

        self.assertNotEqual(state.stage, "PROMOTION_SWEEP")
        self.assertNotEqual(state.stage, "ASSESS_PROMOTION_SWEEP")
        self.assertEqual(state.current_student, pointer)

        retained = cp("whole-student-after-retention", step=pointer.optimizer_step + 1)
        state = grade_loop(course, state, retained)
        reranked_after_learning = {
            c: (8, 8) for c in assessment_capabilities(course, state)
        }
        reranked_after_learning["c.1"] = (21, 25)
        state = assess(
            course, state,
            snapshot(course, retained, reranked_after_learning))

        self.assertEqual(state.stage, "PROMOTION_SWEEP")
        self.assertEqual(state.current_student, retained)

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
