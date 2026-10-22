"""Read-only and disposable proof of parent-vs-trial teacher feedback."""
import math
import random
import unittest
from unittest.mock import patch

import numpy as np
from bilqis_mlx.factory.schedule import (
    ScheduleCapability, ScheduleGrade, ScheduleProgram,
)

from bilqis_mlx.learning.learning_experiment import (
    Settings, paired_outcomes, decide, contextual_pick, observe_context,
    fork_student, commit_trial, sampled_protection, whole_grade_protection,
    missing_grade_capabilities,
    selection_credit, select_source_lesson,
)


def rows():
    return [
        {"id": cap + str(i), "capability": cap,
         "gold": "TRUE" if i % 2 else "FALSE"}
        for cap in ("A.EDGE", "B.XOR", "C.ADD") for i in range(6)
    ]


def predicted(rows_, wrong):
    return {row["id"]: ("TRUE" if row["gold"] == "FALSE" else "FALSE")
            if row["id"] in wrong else row["gold"] for row in rows_}


def schedule_program(*grades):
    return ScheduleProgram(
        program_digest="a" * 64,
        grades=tuple(ScheduleGrade(
            grade,
            tuple(ScheduleCapability(capability, 12)
                  for capability in capabilities),
            (),
            "b" * 64,
        ) for grade, capabilities in grades),
        program_complete=False,
    )


def live_scale_teacher():
    strategies = {
        f"filler-{index:03d}": {"lr": .0001}
        for index in range(492)
    }
    strategies.update({
        "stagnant": {"lr": .0002},
        "alternate": {"lr": .0003},
    })
    return {
        "strategies": strategies,
        "global_stats": {
            "stagnant": {"trials": 28, "reward_sum": -1.91},
            "alternate": {"trials": 41, "reward_sum": 4.34},
        },
        "grade_stats": {
            "C": {
                "stagnant": {"trials": 14, "reward_sum": -.7},
                "alternate": {"trials": 41, "reward_sum": 4.34},
            },
        },
        "events": 14278,
        "causal_experiment": {
            "version": "bilqis.mlx.causal-teacher-experiment/v1",
            "negative_archetypes": [], "events": 10,
            "stagnation": {
                "C.ADD|scope": {
                    "stagnant": {"no_target_gain_streak": 5},
                    "alternate": {"no_target_gain_streak": 0},
                },
            },
            "contexts": {
                "C.ADD|MAIN|scope": {
                    "stagnant": {"trials": 5, "reward_sum": -.25,
                                 "unsafe": 5, "latest": -.05,
                                 "no_target_gain_streak": 5},
                    "alternate": {"trials": 5, "reward_sum": -.5,
                                  "unsafe": 0, "latest": -.1,
                                  "no_target_gain_streak": 0},
                }
            },
        },
    }


class CausalTeacherExperimentTests(unittest.TestCase):
    def test_source_lesson_reserves_weak_semantic_before_policy_fill(self):
        target = {
            "id": "number-three", "capability": "C.NUMBER", "gold": "3",
            "source_id": "source-three", "tokens": [1, 3, 9],
            "answer_kind": "numeric_active",
        }
        current = [
            target,
            {"id": "number-two", "capability": "C.NUMBER", "gold": "2",
             "source_id": "source-two", "tokens": [1, 2, 9],
             "answer_kind": "numeric_active"},
            {"id": "eq-two", "capability": "C.NUMBER", "gold": "TRUE",
             "source_id": "source-two", "tokens": [1, 8, 2, 2, 9],
             "answer_kind": "binary"},
        ]
        prior = [
            {"id": "old-true", "capability": "B.NOT", "gold": "TRUE",
             "source_id": "old-true", "tokens": [1, 4, 9],
             "answer_kind": "binary"},
            {"id": "old-false", "capability": "B.NOT", "gold": "FALSE",
             "source_id": "old-false", "tokens": [1, 5, 9],
             "answer_kind": "binary"},
        ]

        exposures = {target["id"]: 0}
        for seed in range(11, 15):
            picked, control = select_source_lesson(
                current, prior, {"old": 16, "depth": 1, "contrast": 0.},
                targets=[target], target_exposures=exposures,
                reserved_support_slots=2, seed=seed, batch_size=8)
            self.assertIn(target["id"], {row["id"] for row in picked})
            self.assertEqual(control["weakness_targets_requested"], 1)
            self.assertEqual(control["weakness_targets_delivered"], 1)
            exposures[target["id"]] += 1

        self.assertEqual(exposures[target["id"]], 4)

    def test_trainer_defers_missing_peer_inference_until_candidate_target_passes(self):
        from pathlib import Path
        from bilqis_mlx import trainer as trainer
        grade = ("B.IFF", "B.NOT", "B.XOR")
        rows = [{"id": cap + str(i), "capability": cap,
                 "gold": "TRUE"} for cap in (*grade, "A.EDGE") for i in range(2)]
        parent = predicted(rows, {"B.XOR0", "B.NOT0"})
        candidate = dict(parent)
        candidate["B.XOR0"] = "TRUE"
        candidate["B.NOT0"] = "TRUE"
        candidate["B.IFF0"] = "FALSE"
        evaluated = []
        def inference(_mx, identity, chosen, _config, _answers):
            evaluated.append((identity, tuple(row["id"] for row in chosen)))
            truth = parent if identity == "parent" else candidate
            return {row["id"]: truth[row["id"]] for row in chosen}
        with (patch('bilqis_mlx.curriculum.scheduler.assessment_capabilities',
                           return_value=(*grade, "A.EDGE")),
              patch('bilqis_mlx.learning.student_ops._predictions', side_effect=inference),
              patch('bilqis_mlx.runtime.candidate_evidence._fixed_same_grade_rows',
                           return_value=()) as fixed,
              patch("bilqis_mlx.learning.fragile_replay.load_replay_rows",
                    return_value=())):
            school = type("School", (), {"current_student": type(
                "Student", (), {"sha256": "a" * 64, "optimizer_step": 1})()})()
            program = schedule_program(
                ("A", ("A.EDGE",)),
                ("B", grade),
            )
            pair, protected, required, _, _, _, stage = trainer._candidate_grade_evidence(
                None, Path("/not-used"), {"config": {}, "answer_ids": []},
                program, school, "B.XOR", "parent", "candidate", rows,
                {"B.XOR0": parent["B.XOR0"], "B.XOR1": parent["B.XOR1"]},
                Settings())
        self.assertEqual(stage, "COMPLETE_SAME_GRADE")
        self.assertEqual(required, tuple(sorted(grade)))
        self.assertEqual(pair["B.XOR"], {"before": 1, "after": 2, "total": 2})
        self.assertEqual(pair["B.IFF"], {"before": 2, "after": 1, "total": 2})
        self.assertEqual(pair["B.NOT"], {"before": 1, "after": 2, "total": 2})
        self.assertEqual(protected, {"B.IFF", "B.NOT", "A.EDGE"})
        self.assertEqual(len(evaluated), 3)
        self.assertEqual(evaluated[0], ("candidate", ("B.XOR0", "B.XOR1")))
        self.assertTrue(all("B.XOR0" not in call[1] and
                            "B.XOR1" not in call[1] for call in evaluated[1:]))
        fixed.assert_called_once()

    def test_failed_target_and_grade_net_skip_expensive_fixed_replay(self):
        from pathlib import Path
        from bilqis_mlx import trainer as trainer
        grade = ("B.IFF", "B.NOT", "B.XOR")
        rows = [{"id": cap + str(i), "capability": cap,
                 "gold": "TRUE"} for cap in (*grade, "A.EDGE") for i in range(2)]
        parent = predicted(rows, {"B.XOR0", "B.NOT0"})
        candidate = dict(parent)
        candidate["B.XOR0"] = "TRUE"
        candidate["B.IFF0"] = "FALSE"

        # With no target gain, neither peers nor a fixed full-grade exam are
        # evaluated and the unchanged parent can be rejected immediately.
        with (patch('bilqis_mlx.curriculum.scheduler.assessment_capabilities',
                           return_value=(*grade, "A.EDGE")),
              patch('bilqis_mlx.learning.student_ops._predictions',
                           side_effect=lambda _mx, _id, selected, *_:
                           {row["id"]: parent[row["id"]] for row in selected}),
              patch('bilqis_mlx.runtime.candidate_evidence._fixed_same_grade_rows',
                           side_effect=AssertionError("no extra grade test"))):
            program = schedule_program(
                ("A", ("A.EDGE",)),
                ("B", grade),
            )
            small, protected, required, fixed, replay, _, stage = (
                trainer._candidate_grade_evidence(
                    None, Path("/not-used"), {"config": {}, "answer_ids": []},
                    program, object(), "B.XOR", "parent", "candidate", rows,
                    {"B.XOR0": parent["B.XOR0"], "B.XOR1": parent["B.XOR1"]},
                    Settings()))
        self.assertEqual(stage, "TARGET_ONLY_REJECTED")
        self.assertEqual(set(small), {"B.XOR"})
        self.assertEqual(protected, set())
        self.assertEqual(required, ("B.XOR",))
        self.assertEqual(fixed["status"], "NOT_MEASURED")
        self.assertEqual(replay["status"], "NOT_MEASURED")

        # A positive target with negative/tied grade net is also terminal:
        # the full fixed examination must not run for an already-rejected
        # candidate, and only the previously missing grade peers were scored.
        degraded = dict(candidate)
        degraded["B.NOT0"] = "FALSE"
        degraded["B.NOT1"] = "FALSE"
        with (patch('bilqis_mlx.curriculum.scheduler.assessment_capabilities',
                           return_value=(*grade, "A.EDGE")),
              patch('bilqis_mlx.learning.student_ops._predictions',
                           side_effect=lambda _mx, identity, selected, *_:
                           {row["id"]: (parent if identity == "parent"
                                        else degraded)[row["id"]]
                            for row in selected}),
              patch('bilqis_mlx.runtime.candidate_evidence._fixed_same_grade_rows',
                           side_effect=AssertionError("net grade loss must stop"))):
            incomplete, controls, required, fixed, replay, _, stage = (
                trainer._candidate_grade_evidence(
                    None, Path("/not-used"), {"config": {}, "answer_ids": []},
                    program, object(), "B.XOR", "parent", "candidate", rows,
                    {"B.XOR0": parent["B.XOR0"], "B.XOR1": parent["B.XOR1"]},
                    Settings()))
        self.assertEqual(stage, "GRADE_NET_REJECTED")
        self.assertEqual(set(incomplete), {*grade, "A.EDGE"})
        self.assertEqual(sum(incomplete[cap]["after"]-incomplete[cap]["before"]
                             for cap in grade), -1)
        self.assertEqual(controls, {"B.IFF", "B.NOT", "A.EDGE"})
        self.assertEqual(fixed["status"], "NOT_MEASURED")

    def test_b_recovery_uses_whole_school_frontier_even_when_scheduler_is_c(self):
        from pathlib import Path
        from bilqis_mlx import trainer as trainer
        probe = [
            {"id": "probe:iff:0", "capability": "B.IFF", "gold": "TRUE"},
            {"id": "probe:iff:1", "capability": "B.IFF", "gold": "TRUE"},
            {"id": "probe:not:0", "capability": "B.NOT", "gold": "TRUE"},
            {"id": "probe:not:1", "capability": "B.NOT", "gold": "TRUE"},
            {"id": "probe:div:0", "capability": "C.DIV", "gold": "TRUE"},
            {"id": "probe:div:1", "capability": "C.DIV", "gold": "TRUE"},
        ]
        probe_parent = {row["id"]: row["gold"] for row in probe}
        probe_parent["probe:iff:0"] = "FALSE"
        probe_candidate = dict(probe_parent)
        probe_candidate["probe:iff:0"] = "TRUE"
        frontier_rows = [
            {"id": "fixed:iff", "capability": "B.IFF", "gold": "TRUE"},
            {"id": "fixed:not", "capability": "B.NOT", "gold": "TRUE"},
            {"id": "fixed:div", "capability": "C.DIV", "gold": "TRUE"},
        ]
        frontier_parent = {row["id"]: row["gold"] for row in frontier_rows}
        frontier_candidate = dict(frontier_parent)
        frontier_candidate["fixed:not"] = "FALSE"

        def inference(_mx, identity, selected, *_args):
            ids = {row["id"] for row in selected}
            if ids <= set(frontier_parent):
                truth = frontier_candidate if identity == "candidate" else frontier_parent
            else:
                truth = probe_candidate if identity == "candidate" else probe_parent
            return {row["id"]: truth[row["id"]] for row in selected}

        receipt = {
            "config": {}, "answer_ids": [],
            "last_exam": {"cohort_sha256": "a" * 64,
                          "student_sha256": "a" * 64,
                          "optimizer_step": 1},
        }
        school = type("School", (), {
            "grade": "C",
            "current_student": type(
                "Student", (), {"sha256": "a" * 64, "optimizer_step": 1})(),
        })()
        with (patch('bilqis_mlx.curriculum.scheduler.assessment_capabilities',
                           return_value=("B.IFF", "B.NOT", "C.DIV")),
              patch('bilqis_mlx.learning.student_ops._predictions', side_effect=inference),
              patch("bilqis_mlx.fixed_frontier.load_frontier",
                    return_value=(tuple(frontier_rows), frontier_parent)),
              patch("bilqis_mlx.learning.fragile_replay.load_replay_rows",
                    return_value=())):
            program = schedule_program(
                ("A", ("A.EDGE",)),
                ("B", ("B.IFF", "B.NOT")),
                ("C", ("C.DIV",)),
            )
            pair, protected, required, fixed, _, frontier, stage = (
                trainer._candidate_grade_evidence(
                    None, Path("/unused"), receipt, program, school,
                    "B.IFF", "parent", "candidate", probe,
                    {row["id"]: probe_parent[row["id"]]
                     for row in probe if row["capability"] == "B.IFF"},
                    Settings()))
        self.assertEqual(stage, "COMPLETE_SAME_GRADE")
        self.assertEqual(required, ("B.IFF", "B.NOT"))
        self.assertEqual(fixed["status"], "MEASURED")
        self.assertEqual(fixed["grade"], "B")
        self.assertEqual(fixed["before"], 2)
        self.assertEqual(fixed["after"], 1)
        self.assertEqual(frontier["status"], "MEASURED")
        result = decide(
            pair, active_capability="B.IFF", phase="RECOVERY_1",
            protected=protected, settings=Settings(),
            same_grade_capabilities=required, fixed_grade_replay=fixed,
            fixed_frontier_replay=frontier)
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "FIXED_LESSON_GRADE_REGRESSION")

    def test_missing_only_grade_completion_uses_checkpoint_existing_scores(self):
        grade = ("B.AND", "B.IFF", "B.NOT", "B.XOR")
        self.assertEqual(
            missing_grade_capabilities(grade, {"B.XOR": {"before": 8,
                                                       "after": 9, "total": 12},
                                               "B.AND": {"before": 6,
                                                       "after": 6, "total": 12}}),
            ("B.IFF", "B.NOT"))
        self.assertEqual(missing_grade_capabilities(
            grade, {cap: {"before": 0, "after": 0, "total": 1}
                    for cap in grade}), ())
    def test_actual_b_xor_gain_does_not_justify_larger_b_grade_loss(self):
        # Reproduces committed experiment generation 11566: B.XOR +1,
        # B.IFF -1, B.IMPLIES -1, 16 steps incorrectly retained.
        paired = {
            "B.AND": {"before": 6, "after": 6, "total": 6},
            "B.IFF": {"before": 6, "after": 5, "total": 6},
            "B.IMPLIES": {"before": 6, "after": 5, "total": 6},
            "B.NOT": {"before": 6, "after": 6, "total": 6},
            "B.OR": {"before": 6, "after": 6, "total": 6},
            "B.XOR": {"before": 7, "after": 8, "total": 12},
        }
        result = decide(paired, active_capability="B.XOR", phase="RECOVERY_2",
                        protected=set(paired) - {"B.XOR"}, settings=Settings(),
                        mature_grades=frozenset({"A", "B"}),
                        same_grade_capabilities=tuple(paired))
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "SAME_GRADE_NET_REGRESSION")
        self.assertEqual(result["local_correct_delta"], 1)
        self.assertEqual(result["same_grade_net_correct_delta"], -1)

    def test_target_only_gain_with_same_grade_tie_is_not_progress(self):
        paired = {
            "B.XOR": {"before": 7, "after": 8, "total": 12},
            "B.IFF": {"before": 6, "after": 5, "total": 6},
        }
        result = decide(paired, active_capability="B.XOR", phase="RECOVERY_1",
                        protected={"B.IFF"}, settings=Settings(),
                        same_grade_capabilities=("B.IFF", "B.XOR"))
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "NO_POSITIVE_SAME_GRADE_GAIN")
        self.assertEqual(result["same_grade_net_correct_delta"], 0)

    def test_positive_fresh_grade_probe_cannot_hide_fixed_cohort_regression(self):
        paired = {
            "B.IFF": {"before": 8, "after": 9, "total": 12},
            "B.AND": {"before": 6, "after": 6, "total": 6},
        }
        result = decide(
            paired, active_capability="B.IFF", phase="RECOVERY_2",
            protected={"B.AND"}, settings=Settings(),
            same_grade_capabilities=("B.AND", "B.IFF"),
            fixed_grade_replay={"status": "MEASURED", "grade": "B",
                                "before": 59, "after": 56, "total": 72,
                                "cohort_sha256": "a" * 64})
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "FIXED_GRADE_COHORT_REGRESSION")
        self.assertEqual(result["fixed_grade_replay"]["net_correct_delta"], -3)

    def test_fixed_frontier_allows_item_trade_when_grade_improves_and_school_ties(self):
        paired = {
            "C.DIV": {"before": 18, "after": 19, "total": 21},
            "C.MUL": {"before": 21, "after": 21, "total": 21},
        }
        frontier = {
            "status": "MEASURED",
            "cohort_sha256": "a" * 64,
            "rows": 291,
            "before_correct": 287,
            "after_correct": 287,
            "regressions": [{"id": "new_div_error", "capability": "C.DIV"}],
            "repaired": [{"id": "old_div_error", "capability": "C.DIV"}],
            "grades": {
                "C": {"before": 146, "after": 147, "total": 147,
                      "net_correct_delta": 1},
                "B": {"before": 69, "after": 68, "total": 72,
                      "net_correct_delta": -1},
            },
        }
        result = decide(
            paired, active_capability="C.DIV", phase="RECOVERY_1",
            protected={"C.MUL"}, settings=Settings(),
            same_grade_capabilities=("C.DIV", "C.MUL"),
            fixed_grade_replay={"status": "MEASURED", "grade": "C",
                                "before": 146, "after": 147, "total": 147,
                                "cohort_sha256": "a" * 64},
            fixed_frontier_replay=frontier)
        self.assertEqual(result["decision"], "PROVISIONAL")
        self.assertEqual(result["reason"], "PAIRED_SCREEN_WITHIN_BUDGET")
        self.assertEqual(result["fixed_frontier_replay"]["regressions"],
                         frontier["regressions"])
        self.assertEqual(result["fixed_whole_school_net_correct_delta"], 0)

    def test_fixed_frontier_rejects_when_school_loses_more_than_grade_gains(self):
        paired = {
            "B.IFF": {"before": 8, "after": 9, "total": 12},
            "B.NOT": {"before": 10, "after": 10, "total": 12},
        }
        result = decide(
            paired, active_capability="B.IFF", phase="RECOVERY_2",
            protected={"B.NOT"}, settings=Settings(),
            same_grade_capabilities=("B.IFF", "B.NOT"),
            fixed_grade_replay={"status": "MEASURED", "grade": "B",
                                "before": 68, "after": 69, "total": 72,
                                "cohort_sha256": "a" * 64},
            fixed_frontier_replay={
                "status": "MEASURED", "cohort_sha256": "a" * 64,
                "rows": 291, "before_correct": 287, "after_correct": 286,
                "regressions": [
                    {"id": "c1", "capability": "C.DIV"},
                    {"id": "c2", "capability": "C.DIV"},
                ],
                "repaired": [{"id": "b1", "capability": "B.IFF"}],
                "grades": {
                    "B": {"before": 68, "after": 69, "total": 72,
                          "net_correct_delta": 1},
                    "C": {"before": 147, "after": 145, "total": 147,
                          "net_correct_delta": -2},
                },
            })
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "WHOLE_SCHOOL_NET_REGRESSION")
        self.assertEqual(result["fixed_whole_school_net_correct_delta"], -1)

    def test_fixed_frontier_allows_other_grade_repair_when_current_grade_ties(self):
        paired = {
            "B.IFF": {"before": 8, "after": 9, "total": 12},
            "B.NOT": {"before": 10, "after": 10, "total": 12},
        }
        result = decide(
            paired, active_capability="B.IFF", phase="RECOVERY_2",
            protected={"B.NOT"}, settings=Settings(),
            same_grade_capabilities=("B.IFF", "B.NOT"),
            fixed_grade_replay={"status": "MEASURED", "grade": "B",
                                "before": 68, "after": 68, "total": 72,
                                "cohort_sha256": "a" * 64},
            fixed_frontier_replay={
                "status": "MEASURED", "cohort_sha256": "a" * 64,
                "rows": 291, "before_correct": 287, "after_correct": 288,
                "regressions": [],
                "repaired": [{"id": "c1", "capability": "C.DIV"}],
                "grades": {
                    "B": {"before": 68, "after": 68, "total": 72,
                          "net_correct_delta": 0},
                    "C": {"before": 146, "after": 147, "total": 147,
                          "net_correct_delta": 1},
                },
            },
            active_school_grade="B")
        self.assertEqual(result["decision"], "PROVISIONAL")
        self.assertEqual(result["reason"], "PAIRED_SCREEN_WITHIN_BUDGET")

    def test_late_stage_allows_other_grade_gain_when_active_grade_is_flat(self):
        paired = {
            "B.IFF": {"before": 8, "after": 9, "total": 12},
            "B.NOT": {"before": 10, "after": 9, "total": 12},
        }
        result = decide(
            paired, active_capability="B.IFF", phase="RECOVERY_2",
            protected={"B.NOT"}, settings=Settings(),
            same_grade_capabilities=("B.IFF", "B.NOT"),
            fixed_grade_replay={"status": "MEASURED", "grade": "B",
                                "before": 68, "after": 69, "total": 72,
                                "cohort_sha256": "a" * 64},
            fixed_frontier_replay={
                "status": "MEASURED", "cohort_sha256": "a" * 64,
                "rows": 291, "before_correct": 287, "after_correct": 288,
                "regressions": [],
                "repaired": [{"id": "b1", "capability": "B.IFF"}],
                "grades": {
                    "B": {"before": 68, "after": 69, "total": 72,
                          "net_correct_delta": 1},
                    "C": {"before": 146, "after": 146, "total": 147,
                          "net_correct_delta": 0},
                },
            },
            active_school_grade="C")
        self.assertEqual(result["decision"], "PROVISIONAL")
        self.assertEqual(result["reason"], "PAIRED_SCREEN_WITHIN_BUDGET")

    def test_late_stage_rejects_if_active_school_grade_regresses(self):
        paired = {
            "B.IFF": {"before": 8, "after": 9, "total": 12},
            "B.NOT": {"before": 10, "after": 10, "total": 12},
        }
        result = decide(
            paired, active_capability="B.IFF", phase="RECOVERY_2",
            protected={"B.NOT"}, settings=Settings(),
            same_grade_capabilities=("B.IFF", "B.NOT"),
            fixed_grade_replay={"status": "MEASURED", "grade": "B",
                                "before": 68, "after": 70, "total": 72,
                                "cohort_sha256": "a" * 64},
            fixed_frontier_replay={
                "status": "MEASURED", "cohort_sha256": "a" * 64,
                "rows": 291, "before_correct": 287, "after_correct": 288,
                "regressions": [{"id": "c1", "capability": "C.DIV"}],
                "repaired": [
                    {"id": "b1", "capability": "B.IFF"},
                    {"id": "b2", "capability": "B.NOT"},
                ],
                "grades": {
                    "B": {"before": 68, "after": 70, "total": 72,
                          "net_correct_delta": 2},
                    "C": {"before": 146, "after": 145, "total": 147,
                          "net_correct_delta": -1},
                },
            },
            active_school_grade="C")
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "ACTIVE_SCHOOL_GRADE_REGRESSION")

    def test_late_stage_allows_frontier_without_fully_withheld_logical_grade(self):
        paired = {
            "C.MUL": {"before": 17, "after": 18, "total": 21},
            "C.DIV": {"before": 18, "after": 18, "total": 21},
        }
        result = decide(
            paired, active_capability="C.MUL", phase="RECOVERY_2",
            protected={"C.DIV"}, settings=Settings(),
            same_grade_capabilities=("C.MUL", "C.DIV"),
            fixed_grade_replay={"status": "MEASURED", "grade": "C",
                                "before": 139, "after": 140, "total": 147,
                                "cohort_sha256": "a" * 64},
            fixed_frontier_replay={
                "status": "MEASURED", "cohort_sha256": "a" * 64,
                "rows": 219, "before_correct": 209, "after_correct": 210,
                "regressions": [],
                "repaired": [{"id": "c1", "capability": "C.MUL"}],
                "grades": {
                    "A": {"before": 70, "after": 70, "total": 72,
                          "net_correct_delta": 0},
                    "C": {"before": 139, "after": 140, "total": 147,
                          "net_correct_delta": 1},
                },
            },
            active_school_grade="B")
        self.assertEqual(result["decision"], "PROVISIONAL")
        self.assertEqual(result["reason"], "PAIRED_SCREEN_WITHIN_BUDGET")

    def test_all_target_grade_capabilities_must_be_measured(self):
        paired = {"B.XOR": {"before": 7, "after": 8, "total": 12}}
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_SAME_GRADE_PROBE"):
            decide(paired, active_capability="B.XOR", phase="MAIN",
                   protected=set(), settings=Settings(),
                   same_grade_capabilities=("B.IFF", "B.XOR"))

    def test_six_b_capabilities_all_scored_with_bounded_cross_grade_probes(self):
        admitted = {f"B.{name}" for name in (
            "AND", "IFF", "IMPLIES", "NOT", "OR", "XOR")}
        admitted.update({f"A.{i}" for i in range(6)})
        admitted.update({f"C.{i}" for i in range(7)})
        selected = whole_grade_protection(
            admitted, "B.XOR", {}, cap_limit=8, rotation=11)
        self.assertEqual(len(selected), 8)
        self.assertEqual({cap for cap in selected if cap.startswith("B.")},
                         admitted.intersection({cap for cap in admitted
                                                if cap.startswith("B.")}) - {"B.XOR"})
        self.assertEqual({cap.split(".")[0] for cap in selected}, {"A", "B", "C"})
        too_many = {f"B.{i}" for i in range(10)}
        too_many.update({f"A.{i}" for i in range(6)})
        large_grade = whole_grade_protection(
            too_many, "B.0", {}, cap_limit=8, rotation=0)
        self.assertEqual({cap for cap in large_grade if cap.startswith("B.")},
                         {f"B.{i}" for i in range(1, 10)})
        self.assertEqual(len(large_grade), 11)

    def test_primary_bandit_receives_negative_rejection_credit_instead_of_zero(self):
        rejected = {"decision": "REJECT"}
        credit = {"teacher_context_reward": -0.05}
        self.assertEqual(selection_credit(0.0, rejected, credit), -0.05)
        accepted = {"decision": "PROVISIONAL"}
        self.assertEqual(selection_credit(0.0, accepted,
                                          {"teacher_context_reward": 1/21}), 1/21)
        self.assertEqual(selection_credit(0.125, None, None), 0.125)
        with self.assertRaisesRegex(ValueError, "INVALID_SELECTION_CREDIT"):
            selection_credit(0.0, rejected, {"teacher_context_reward": 0.0})

    def test_vulnerable_boolean_anchor_flip_is_diagnostic_not_an_item_veto(self):
        paired = {"C.SUCCESSOR": {"before": 20, "after": 21, "total": 21},
                  "B.XOR": {"before": 6, "after": 6, "total": 6}}
        replay = {"status": "MEASURED", "cohort_sha256": "a" * 64,
                  "rows": 24, "regressions": [{"id": "xor_true_case", "capability": "B.XOR"}],
                  "repaired": 1}
        trial = decide(paired, active_capability="C.SUCCESSOR", phase="MAIN",
                       protected={"B.XOR"}, settings=Settings(),
                       mature_grades=frozenset({"A", "B"}), fragile_replay=replay)
        self.assertEqual(trial["decision"], "REJECT")
        self.assertEqual(trial["reason"], "FRAGILE_COMPOSITION_REPLAY_REGRESSION")
        self.assertEqual(trial["fragile_replay"]["regressions"], replay["regressions"])
        teacher = {"strategies": {"p": {"lr": 0.0001}}}
        observe_context(teacher, capability="C.SUCCESSOR", phase="MAIN",
                        policy_key="p", decision=trial, local_gain=0.03)
        strategy = teacher["causal_experiment"]["contexts"]["C.SUCCESSOR|MAIN|"]["p"]
        self.assertEqual(strategy["unsafe"], 1)
        self.assertEqual(strategy["latest_fragile_replay"]["regressions"], 1)
        replay["regressions"] = []
        safe = decide(paired, active_capability="C.SUCCESSOR", phase="MAIN",
                      protected={"B.XOR"}, settings=Settings(), fragile_replay=replay)
        self.assertEqual(safe["decision"], "PROVISIONAL")

    def setUp(self):
        self.rows = rows()
        self.before = predicted(self.rows, {"C.ADD0", "C.ADD1", "C.ADD2"})

    def test_one_parent_two_outcomes_and_phase_specific_gate(self):
        after = predicted(self.rows, {
            "B.XOR0", "B.XOR1", "B.XOR2", "C.ADD0"})
        scores = paired_outcomes(self.rows, self.before, after)
        self.assertEqual(scores["C.ADD"]["after"]-scores["C.ADD"]["before"], 2)
        self.assertEqual(scores["B.XOR"]["before"]-scores["B.XOR"]["after"], 3)
        settings = Settings(probe_each=6, mature_max_loss=2, introduction_extra_loss=2)
        provisional = decide(scores, active_capability="C.ADD", phase="MAIN",
                             protected={"A.EDGE", "B.XOR"}, settings=settings)
        mature_main = decide(scores, active_capability="C.ADD", phase="MAIN",
                             protected={"A.EDGE", "B.XOR"}, settings=settings,
                             mature_grades=frozenset({"A", "B"}))
        rejected = decide(scores, active_capability="C.ADD", phase="RECOVERY_1",
                          protected={"A.EDGE", "B.XOR"}, settings=settings)
        self.assertEqual(provisional["decision"], "PROVISIONAL")
        self.assertEqual(mature_main["decision"], "REJECT")
        self.assertEqual(mature_main["exceeded"], {"B.XOR": 3})
        self.assertEqual(mature_main["protected_tolerances"]["B.XOR"], 2)
        self.assertEqual(rejected["decision"], "REJECT")
        self.assertEqual(rejected["exceeded"], {"B.XOR": 3})
        self.assertFalse(rejected["exact_complete_exam_qualification"])
        self.assertEqual(rejected["paired_scores_sha256"], provisional["paired_scores_sha256"])
        with self.assertRaisesRegex(ValueError, "NOT_MEASURED"):
            decide(scores, active_capability="C.ADD", phase="RECOVERY_1",
                   protected={"A.MAPS"}, settings=settings)

    def test_teacher_context_learns_negative_evidence_without_mutating_prior(self):
        from copy import deepcopy
        settings = Settings()
        scores = paired_outcomes(self.rows, self.before,
                                 predicted(self.rows, {"B.XOR0", "B.XOR1", "B.XOR2"}))
        evidence = decide(scores, active_capability="C.ADD", phase="RECOVERY_2",
                          protected={"B.XOR"}, settings=settings)
        teacher = {"strategies": {"positive": {"lr": .0001}, "negative": {"lr": .0002}},
                   "global_stats": {"positive": {"trials": 12, "reward_sum": 3.},
                                    "negative": {"trials": 8, "reward_sum": 5.}}}
        historic = deepcopy(teacher["global_stats"])
        for _ in range(2):
            result = observe_context(teacher, capability="C.ADD",
                                     phase="RECOVERY_2", policy_key="negative",
                                     decision=evidence, local_gain=.1)
        self.assertLess(result["teacher_context_reward"], 0)
        self.assertEqual(teacher["global_stats"], historic)
        self.assertEqual(len(teacher["causal_experiment"]["negative_archetypes"]), 1)

        class Legacy:
            @staticmethod
            def pick(_t, _grade, _rng):
                return "negative", _t["strategies"]["negative"]

        accepted = decide(paired_outcomes(self.rows, self.before,
                            predicted(self.rows, {"C.ADD0"})),
                          active_capability="C.ADD", phase="RECOVERY_2",
                          protected={"B.XOR"}, settings=settings)
        for _ in range(3):
            observe_context(teacher, capability="C.ADD", phase="RECOVERY_2",
                            policy_key="positive", decision=accepted, local_gain=.4)
        pick, _ = contextual_pick(Legacy, teacher, "C.ADD", "RECOVERY_2", random.Random(2))
        self.assertEqual(pick, "positive")

    def test_repeated_no_target_gain_demotes_policy_until_real_gain_resets_streak(self):
        teacher = live_scale_teacher()
        class Legacy:
            @staticmethod
            def pick(_teacher, _grade, _rng):
                return "stagnant", _teacher["strategies"]["stagnant"]

        self.assertEqual(len(teacher["strategies"]), 494)
        picked, _ = contextual_pick(
            Legacy, teacher, "C.ADD", "MAIN", random.Random(2),
            curriculum_scope="scope")
        self.assertEqual(picked, "alternate")

        no_gain = decide({
            "C.ADD": {"before": 3, "after": 3, "total": 6},
        }, active_capability="C.ADD", phase="MAIN", protected=set(),
            settings=Settings())
        no_gain_credit = observe_context(
            teacher, capability="C.ADD", phase="MAIN",
            policy_key="stagnant", decision=no_gain,
            local_gain=0., curriculum_scope="scope")
        self.assertLessEqual(
            no_gain_credit["teacher_selection_reward"],
            0.-no_gain_credit["inherited_exploration_credit"])
        self.assertEqual(
            selection_credit(0., no_gain, no_gain_credit),
            no_gain_credit["teacher_selection_reward"])
        next_log = math.log(teacher["events"] + 4)
        stagnant_rank = (
            (-.7 + no_gain_credit["teacher_selection_reward"]) / 15
            + .6 * math.sqrt(next_log / 16)
        )
        productive_rank = (
            4.34 / 41 + .6 * math.sqrt(next_log / 42)
        )
        self.assertLess(stagnant_rank, productive_rank)
        self.assertEqual(
            teacher["causal_experiment"]["contexts"]["C.ADD|MAIN|scope"]
                   ["stagnant"]["no_target_gain_streak"], 6)
        self.assertEqual(
            teacher["causal_experiment"]["stagnation"]["C.ADD|scope"]
                   ["stagnant"]["no_target_gain_streak"], 6)

        recovery_no_gain = dict(no_gain, phase="RECOVERY_1")
        observe_context(teacher, capability="C.ADD", phase="RECOVERY_1",
                        policy_key="stagnant", decision=recovery_no_gain,
                        local_gain=0., curriculum_scope="scope")
        self.assertEqual(
            teacher["causal_experiment"]["stagnation"]["C.ADD|scope"]
                   ["stagnant"]["no_target_gain_streak"], 7)

        gain = decide({
            "C.ADD": {"before": 3, "after": 4, "total": 6},
        }, active_capability="C.ADD", phase="MAIN", protected=set(),
            settings=Settings())
        recovery_gain = dict(gain, phase="RECOVERY_2")
        observe_context(teacher, capability="C.ADD", phase="RECOVERY_2",
                        policy_key="stagnant", decision=recovery_gain,
                        local_gain=.1, curriculum_scope="scope")
        self.assertEqual(
            teacher["causal_experiment"]["contexts"]["C.ADD|MAIN|scope"]
                   ["stagnant"]["no_target_gain_streak"], 6)
        self.assertEqual(
            teacher["causal_experiment"]["contexts"]["C.ADD|RECOVERY_2|scope"]
                   ["stagnant"]["no_target_gain_streak"], 0)
        self.assertEqual(
            teacher["causal_experiment"]["stagnation"]["C.ADD|scope"]
                   ["stagnant"]["no_target_gain_streak"], 0)

    def test_provisional_protected_loss_becomes_typed_negative_evidence(self):
        scores = paired_outcomes(self.rows, self.before,
                                 predicted(self.rows, {"B.XOR0", "C.ADD0"}))
        decision = decide(scores, active_capability="C.ADD", phase="RECOVERY_1",
                          protected={"B.XOR"}, settings=Settings())
        self.assertEqual(decision["decision"], "PROVISIONAL")
        self.assertEqual(decision["worst_protected_loss"], 1)
        teacher = {"strategies": {"p": {"lr": .0001}}}
        observed = observe_context(teacher, capability="C.ADD", phase="RECOVERY_1",
                                   policy_key="p", decision=decision, local_gain=0.)
        self.assertLess(observed["teacher_context_reward"], 0.)
        self.assertEqual(teacher["causal_experiment"]["negative_archetypes"][0]["outcome"],
                         "ACCEPTED_WITH_MEASURED_PROTECTED_LOSS")
        self.assertEqual(teacher["causal_experiment"]["contexts"]["C.ADD|RECOVERY_1|"]["p"]["unsafe"], 0)

    def test_recovery_rejects_small_unproductive_cumulative_regression(self):
        scores = paired_outcomes(self.rows, self.before,
                                 predicted(self.rows, {"B.XOR0", "C.ADD0", "C.ADD1", "C.ADD2"}))
        mature = decide(scores, active_capability="C.ADD", phase="RECOVERY_2",
                        protected={"B.XOR"}, settings=Settings())
        self.assertEqual(mature["worst_protected_loss"], 1)
        self.assertEqual(mature["local_correct_delta"], 0)
        self.assertEqual(mature["decision"], "REJECT")
        self.assertEqual(mature["reason"], "NO_MEASURABLE_TARGET_GAIN")
        developmental = decide(scores, active_capability="C.ADD", phase="MAIN",
                               protected={"B.XOR"}, settings=Settings())
        self.assertEqual(developmental["decision"], "REJECT")
        self.assertEqual(developmental["reason"], "NO_MEASURABLE_TARGET_GAIN")

    def test_no_gain_must_reject_in_every_phase_even_if_older_skills_improve(self):
        # C stays at 3/6; B improves. A global net-positive vote is not
        # evidence that the targeted C capability learned anything.
        scores = {
            "C.ADD": {"before": 3, "after": 3, "total": 6},
            "B.XOR": {"before": 4, "after": 5, "total": 6},
        }
        for phase in ("MAIN", "RECOVERY_1", "RECOVERY_2"):
            with self.subTest(phase=phase):
                outcome = decide(scores, active_capability="C.ADD",
                                 phase=phase, protected={"B.XOR"},
                                 settings=Settings(), mature_grades=frozenset({"B"}))
                self.assertEqual(outcome["decision"], "REJECT")
                self.assertEqual(outcome["reason"], "NO_MEASURABLE_TARGET_GAIN")
                self.assertEqual(outcome["local_correct_delta"], 0)
                self.assertEqual(outcome["active_probe_before"], 3)
                self.assertEqual(outcome["active_probe_after"], 3)
                self.assertEqual(outcome["active_probe_total"], 6)
                self.assertEqual(outcome["protected_net_correct_delta"], 1)

    def test_target_regression_rejected_even_with_positive_other_grade(self):
        outcome = decide({
            "C.ADD": {"before": 4, "after": 3, "total": 6},
            "B.XOR": {"before": 4, "after": 6, "total": 6},
        }, active_capability="C.ADD", phase="MAIN", protected={"B.XOR"},
            settings=Settings(), mature_grades=frozenset({"B"}))
        self.assertEqual(outcome["reason"], "NO_MEASURABLE_TARGET_GAIN")
        self.assertEqual(outcome["local_correct_delta"], -1)
        self.assertEqual(outcome["decision"], "REJECT")

    def test_late_stage_protection_scales_with_probe_and_vetoes_concentrated_loss(self):
        settings = Settings(probe_each=6, mature_max_loss=1,
                            introduction_extra_loss=2)
        fixed = {"status": "MEASURED", "grade": "C",
                 "cohort_sha256": "a" * 64,
                 "before": 50, "after": 53, "total": 66}
        frontier = {"status": "MEASURED", "before_correct": 151,
                    "after_correct": 154, "rows": 186,
                    "regressions": [], "repaired": [],
                    "grades": {"C": {"before": 50, "after": 53,
                                      "total": 66}}}
        acceptable = decide({
            "C.COUNT": {"before": 14, "after": 23, "total": 33},
            "C.NUMBER": {"before": 31, "after": 29, "total": 33},
        }, active_capability="C.COUNT", phase="RECOVERY_1",
            protected={"C.NUMBER"}, settings=settings,
            same_grade_capabilities=("C.COUNT", "C.NUMBER"),
            fixed_grade_replay=fixed, fixed_frontier_replay=frontier,
            active_school_grade="C")
        self.assertEqual(acceptable["protected_tolerances"], {"C.NUMBER": 5})
        self.assertEqual(acceptable["exceeded"], {})
        self.assertEqual(acceptable["decision"], "PROVISIONAL")

        concentrated = decide({
            "C.COUNT": {"before": 14, "after": 23, "total": 33},
            "C.NUMBER": {"before": 33, "after": 27, "total": 33},
        }, active_capability="C.COUNT", phase="RECOVERY_1",
            protected={"C.NUMBER"}, settings=settings,
            same_grade_capabilities=("C.COUNT", "C.NUMBER"),
            fixed_grade_replay=fixed, fixed_frontier_replay=frontier,
            active_school_grade="C")
        self.assertEqual(concentrated["protected_tolerances"], {"C.NUMBER": 5})
        self.assertEqual(concentrated["exceeded"], {"C.NUMBER": 6})
        self.assertEqual(concentrated["reason"], "PROTECTED_CAPABILITY_REGRESSION")
        self.assertEqual(concentrated["decision"], "REJECT")

    def test_mature_grades_never_inherit_developmental_loss_budget(self):
        rows = {
            "C.ADD": {"before": 3, "after": 4, "total": 6},
            "B.XOR": {"before": 6, "after": 4, "total": 6},
            "C.SUB": {"before": 6, "after": 4, "total": 6},
        }
        settings = Settings(probe_each=6, mature_max_loss=1,
                            introduction_extra_loss=2)
        result = decide(rows, active_capability="C.ADD", phase="MAIN",
                        protected={"B.XOR", "C.SUB"}, settings=settings,
                        mature_grades=frozenset({"A", "B"}))
        self.assertEqual(result["local_correct_delta"], 1)
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "PROTECTED_CAPABILITY_REGRESSION")
        self.assertEqual(result["exceeded"], {"B.XOR": 2})
        self.assertEqual(result["protected_tolerances"], {"B.XOR": 1, "C.SUB": 3})
        self.assertEqual(result["mature_protected_capabilities"], ["B.XOR"])
        rows["B.XOR"] = {"before": 6, "after": 5, "total": 6}
        passing = decide(rows, active_capability="C.ADD", phase="MAIN",
                         protected={"B.XOR", "C.SUB"}, settings=settings,
                         mature_grades=frozenset({"A", "B"}))
        self.assertEqual(passing["decision"], "REJECT")
        self.assertEqual(passing["reason"], "SAME_GRADE_NET_REGRESSION")
        self.assertEqual(passing["same_grade_net_correct_delta"], -1)
        rows["C.SUB"] = {"before": 6, "after": 6, "total": 6}
        passing = decide(rows, active_capability="C.ADD", phase="MAIN",
                         protected={"B.XOR", "C.SUB"}, settings=settings,
                         mature_grades=frozenset({"A", "B"}))
        self.assertEqual(passing["decision"], "PROVISIONAL")

    def test_teacher_learns_rejected_nonprogress_without_legacy_reward_rewrite(self):
        from copy import deepcopy
        decision = decide({
            "C.ADD": {"before": 3, "after": 3, "total": 6},
            "B.XOR": {"before": 6, "after": 6, "total": 6},
        }, active_capability="C.ADD", phase="MAIN", protected={"B.XOR"},
            settings=Settings(), mature_grades=frozenset({"B"}))
        teacher = {"strategies": {"p": {"lr": .0001}},
                   "global_stats": {"p": {"trials": 9, "reward_sum": 3.}}}
        historic = deepcopy(teacher["global_stats"])
        outcome = observe_context(teacher, capability="C.ADD", phase="MAIN",
                                  policy_key="p", decision=decision,
                                  local_gain=.75)
        self.assertLess(outcome["teacher_context_reward"], 0.)
        self.assertEqual(teacher["global_stats"], historic)
        self.assertEqual(teacher["causal_experiment"]["events"], 1)
        self.assertEqual(teacher["causal_experiment"]["contexts"]["C.ADD|MAIN|"]["p"]["unsafe"], 1)
        self.assertEqual(teacher["causal_experiment"]["negative_archetypes"][0]["outcome"],
                         "REJECTED_UPDATE")

    def test_incomplete_or_duplicate_paired_cohort_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "INCOMPLETE"):
            paired_outcomes(self.rows, self.before, {})
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            paired_outcomes(self.rows+self.rows[:1], self.before, self.before)

    def test_bounded_protection_rotates_thousands_of_capabilities(self):
        admitted={f"{grade}.CAP{i:04d}" for grade in "ABCDEFGH"
                  for i in range(500)}
        admitted.add("C.ACTIVE")
        scores={cap: {"correct":1, "total":6} if cap.endswith("0011")
                else {"correct":6, "total":6} for cap in admitted}
        samples=[sampled_protection(admitted,"C.ACTIVE",scores,
                   cap_limit=8,rotation=turn) for turn in range(30)]
        self.assertTrue(all(len(sample)==8 for sample in samples))
        self.assertTrue(all({cap.partition(".")[0] for cap in sample}
                            == set("ABCDEFGH") for sample in samples))
        self.assertGreater(len(set().union(*samples)),8)

    def test_parent_adamw_remains_unchanged_until_trial_committed(self):
        import mlx.core as mx
        import mlx.optimizers as optim
        mx.set_default_device(mx.cpu)
        weights = {"embedding.weight": mx.array(np.arange(12).reshape(3,4).astype(np.float32))}
        parent = optim.AdamW(learning_rate=.00013, bias_correction=True)
        parent.update(weights, {"embedding.weight": mx.zeros_like(weights["embedding.weight"])})
        mx.eval(weights,parent.state)
        parent_weight = np.asarray(weights["embedding.weight"]).copy()
        parent_moment = np.asarray(parent.state["embedding.weight"]["m"]).copy()
        parent_step = int(parent.state["step"].item())
        branch, branch_opt = fork_student(mx, weights, parent)
        branch_opt.update(branch, {"embedding.weight": mx.ones_like(branch["embedding.weight"])})
        mx.eval(branch,branch_opt.state)
        self.assertEqual(int(parent.state["step"].item()), parent_step)
        np.testing.assert_array_equal(np.asarray(weights["embedding.weight"]), parent_weight)
        np.testing.assert_array_equal(np.asarray(parent.state["embedding.weight"]["m"]), parent_moment)
        self.assertNotEqual(int(branch_opt.state["step"].item()), parent_step)
        commit_trial(weights, parent, branch, branch_opt)
        self.assertEqual(int(parent.state["step"].item()), parent_step+1)
        self.assertFalse(np.array_equal(np.asarray(weights["embedding.weight"]), parent_weight))



class DebtRehearsalTests(unittest.TestCase):
    def test_only_recorded_earlier_debt_joins_graduated_rehearsal(self):
        from bilqis_mlx.learning.learning_experiment import earlier_grade_capabilities

        program = schedule_program(
            ("A", ("A.IDENTITY", "A.MAPS")),
            ("B", ("B.XOR",)),
            ("D", ("D.EVENT_OCCURRENCE",)),
        )
        debt = ("A.MAPS", "B.XOR", "D.EVENT_OCCURRENCE", "E.UNKNOWN")
        self.assertEqual(
            earlier_grade_capabilities(
                program, {}, "B.XOR", carried_mastery_debt=debt),
            ("A.MAPS",),
        )
        self.assertEqual(
            earlier_grade_capabilities(
                program, {"A": object()}, "D.EVENT_OCCURRENCE",
                carried_mastery_debt=debt),
            ("A.IDENTITY", "A.MAPS", "B.XOR"),
        )
        self.assertEqual(earlier_grade_capabilities(program, {}, "B.XOR"), ())


if __name__ == "__main__":
    unittest.main()
