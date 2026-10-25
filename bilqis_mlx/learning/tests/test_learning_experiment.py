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
    selection_credit, select_source_lesson, candidate_step_budget,
    _active_effective_strategy_keys, _effective_policy_key,
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


def strategy_population_teacher(count=24):
    policies = []
    for old in (4, 8, 12, 16, 20):
        for depth in (1, 3):
            for contrast in (0., .5):
                for lr in (.00004, .00008, .00013, .0002, .0003):
                    for distill in (0., .15, .35, .65):
                        policies.append({
                            "old": old, "preview": 0, "depth": depth,
                            "contrast": contrast, "lr": lr,
                            "distill": distill,
                        })
    strategies = {
        f"policy-{index:03d}": policy
        for index, policy in enumerate(policies[:count])
    }
    stats = {
        key: {"trials": 10, "reward_sum": 0., "reward_ema": 0., "latest": 0.}
        for key in strategies
    }
    return {
        "strategies": strategies,
        "global_stats": stats,
        "grade_stats": {"C": {key: dict(value) for key, value in stats.items()}},
        "events": 30,
        "mutations": 0,
        "causal_experiment": {
            "version": "bilqis.mlx.causal-teacher-experiment/v1",
            "negative_archetypes": [], "events": 0, "contexts": {},
        },
    }


class CausalTeacherExperimentTests(unittest.TestCase):
    def test_fresh_support_yields_capacity_to_reserved_retention_rows(self):
        from bilqis_mlx.runtime.candidate_evidence import _inject_preservation_rows

        target = {
            "id": "miss", "capability": "C.MUL", "gold": "3",
            "source_id": "historic", "tokens": [1, 9],
            "answer_kind": "numeric_active",
        }
        current = [target]
        current.extend([
            {"id": f"long-{index}", "capability": "C.MUL", "gold": str(index),
             "source_id": "long", "tokens": [1, 2, 3, 4, index],
             "answer_kind": "numeric_active"}
            for index in range(3)
        ])
        current.extend([
            {"id": f"short-{index}", "capability": "C.MUL", "gold": str(index),
             "source_id": "short", "tokens": [1, index],
             "answer_kind": "numeric_active"}
            for index in range(2)
        ])
        preservation = [
            {"id": f"preserve-{index}", "capability": "B.XOR",
             "gold": "TRUE" if index else "FALSE", "tokens": [7, index]}
            for index in range(2)
        ]

        picked, control = select_source_lesson(
            current, [], {"old": 0, "depth": 3, "contrast": 0.},
            targets=[target], target_exposures={target["id"]: 0},
            reserved_support_slots=len(preservation), seed=17, batch_size=4)
        injected, delivered = _inject_preservation_rows(
            picked, preservation,
            reserved_ids=set(control["fresh_support_ids"]) |
                         set(control["weakness_target_ids"]))

        self.assertEqual(control["fresh_support_delivered"], 2)
        self.assertEqual(len(injected), 4)
        self.assertEqual({row["id"] for row in delivered},
                         {"preserve-0", "preserve-1"})

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

    def test_champion_priority_target_wins_limited_weakness_slot(self):
        champion = {
            "id": "z-champion", "capability": "C.SUB", "gold": "3",
            "source_id": "champion", "tokens": [1, 3, 9],
            "answer_kind": "numeric_active",
        }
        ordinary = {
            "id": "a-ordinary", "capability": "C.SUB", "gold": "2",
            "source_id": "ordinary", "tokens": [1, 2, 9],
            "answer_kind": "numeric_active",
        }
        current = [
            champion, ordinary,
            {"id": "n1", "capability": "C.SUB", "gold": "1",
             "source_id": "n1", "tokens": [1, 1, 9],
             "answer_kind": "numeric_active"},
            {"id": "n0", "capability": "C.SUB", "gold": "0",
             "source_id": "n0", "tokens": [1, 0, 9],
             "answer_kind": "numeric_active"},
        ]
        _picked, control = select_source_lesson(
            current, [], {"old": 0, "depth": 1, "contrast": 0.},
            targets=[ordinary, champion],
            priority_target_ids={champion["id"]},
            target_exposures={ordinary["id"]: 0, champion["id"]: 0},
            reserved_support_slots=2, seed=7, batch_size=4)
        self.assertEqual(control["weakness_target_ids"], [champion["id"]])
        self.assertEqual(control["priority_weakness_targets_delivered"], 1)

    def test_typed_weakness_replay_preserves_one_complete_fresh_source_bundle(self):
        current = []
        for group in range(6):
            source_id = f"fresh-{group}"
            current.extend([
                {"id": f"{source_id}-numeric", "capability": "C.COUNT",
                 "gold": str(group), "source_id": source_id,
                 "tokens": [1, group, 9], "answer_kind": "numeric_active"},
                {"id": f"{source_id}-true", "capability": "C.COUNT",
                 "gold": "TRUE", "source_id": source_id,
                 "tokens": [1, group, 7, 9], "answer_kind": "binary"},
                {"id": f"{source_id}-false", "capability": "C.COUNT",
                 "gold": "FALSE", "source_id": source_id,
                 "tokens": [1, group, 8, 9], "answer_kind": "binary"},
            ])
        targets = [
            {"id": f"miss-{index}", "capability": "C.COUNT",
             "gold": "FALSE", "source_id": f"historic-{index}",
             "tokens": [1, 99, index, 9], "answer_kind": "binary"}
            for index in range(24)
        ]
        prior = [
            {"id": f"old-{index}", "capability": "A.IDENTITY",
             "gold": "TRUE" if index % 2 else "FALSE",
             "source_id": f"old-{index}", "tokens": [1, index, 9],
             "answer_kind": "binary"}
            for index in range(32)
        ]

        picked, control = select_source_lesson(
            [*current, *targets], prior,
            {"old": 16, "depth": 1, "contrast": 0.},
            targets=targets,
            target_exposures={row["id"]: 0 for row in targets},
            seed=41, batch_size=32)

        support_ids = set(control["fresh_support_ids"])
        self.assertEqual(len(support_ids), 3)
        support = [row for row in current if row["id"] in support_ids]
        self.assertEqual(len({row["source_id"] for row in support}), 1)
        self.assertEqual(
            {(row["answer_kind"], row["gold"]) for row in support},
            {("numeric_active", support[0]["source_id"].split("-")[-1]),
             ("binary", "TRUE"), ("binary", "FALSE")})
        self.assertTrue(support_ids <= {row["id"] for row in picked})
        self.assertLessEqual(control["weakness_targets_delivered"], 13)
        self.assertGreaterEqual(
            len([row for row in picked if row["id"] in {r["id"] for r in current}]),
            3)

    def test_weakness_replay_yields_when_fresh_support_fills_current_slice(self):
        source_id = "fresh-complete-family"
        fresh_family = [
            {"id": f"{source_id}-{index}", "capability": "C.SUCCESSOR",
             "gold": str(index), "source_id": source_id,
             "tokens": [1, index, 9], "answer_kind": "numeric_active"}
            for index in range(8)
        ]
        target = {
            "id": "historic-miss", "capability": "C.SUCCESSOR",
            "gold": "FALSE", "source_id": "historic-miss",
            "tokens": [1, 99, 9], "answer_kind": "binary",
        }
        prior = [
            {"id": f"old-{index}", "capability": "B.AND",
             "gold": "TRUE" if index % 2 else "FALSE",
             "source_id": f"old-{index}", "tokens": [1, index, 9],
             "answer_kind": "binary"}
            for index in range(32)
        ]

        picked, control = select_source_lesson(
            [*fresh_family, target], prior,
            {"old": 24, "depth": 1, "contrast": 0.},
            targets=[target], target_exposures={target["id"]: 0},
            seed=43, batch_size=32)

        self.assertEqual(len(picked), 32)
        self.assertEqual(control["fresh_support_delivered"], 8)
        self.assertEqual(control["weakness_targets_requested"], 0)
        self.assertEqual(control["weakness_targets_delivered"], 0)
        self.assertNotIn(target["id"], {row["id"] for row in picked})

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
            protected_frontier_grade="B")
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
            protected_frontier_grade="C")
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
            protected_frontier_grade="C")
        self.assertEqual(result["decision"], "REJECT")
        self.assertEqual(result["reason"], "ACTIVE_SCHOOL_GRADE_REGRESSION")

    def test_frontier_allows_item_flux_when_frontier_aggregate_holds(self):
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
                "rows": 291, "before_correct": 287, "after_correct": 288,
                "regressions": [{"id": "c-old-right-now-wrong",
                                 "capability": "C.DIV"}],
                "repaired": [{"id": "c-old-wrong-now-right",
                              "capability": "C.MUL"},
                             {"id": "b-target-repair",
                              "capability": "B.IFF"}],
                "grades": {
                    "B": {"before": 68, "after": 69, "total": 72,
                          "net_correct_delta": 1},
                    "C": {"before": 146, "after": 146, "total": 147,
                          "net_correct_delta": 0},
                },
            },
            protected_frontier_grade="C")
        self.assertEqual(result["decision"], "PROVISIONAL")
        self.assertEqual(result["reason"], "PAIRED_SCREEN_WITHIN_BUDGET")
        self.assertEqual(result["protected_frontier_grade"], "C")
        self.assertEqual(result["protected_frontier_grade_net_correct_delta"], 0)

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
            protected_frontier_grade="B")
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

    def test_single_retained_context_success_is_immediately_exploitable(self):
        teacher = {
            "strategies": {
                "legacy": {"lr": .0002},
                "retained": {"lr": .00008},
            },
            "global_stats": {
                "legacy": {"trials": 20, "reward_sum": 2., "reward_ema": .1,
                           "latest": .1},
                "retained": {"trials": 20, "reward_sum": 2., "reward_ema": .1,
                             "latest": .1},
            },
            "grade_stats": {},
            "events": 40,
        }

        rejected = decide({
            "C.ADD": {"before": 3, "after": 3, "total": 6},
        }, active_capability="C.ADD", phase="RECOVERY_2", protected=set(),
            settings=Settings())
        observe_context(
            teacher, capability="C.ADD", phase="RECOVERY_2",
            policy_key="legacy", decision=rejected, local_gain=0.,
            curriculum_scope="scope")

        retained = decide({
            "C.ADD": {"before": 3, "after": 5, "total": 6},
        }, active_capability="C.ADD", phase="RECOVERY_2", protected=set(),
            settings=Settings())
        self.assertEqual(retained["decision"], "PROVISIONAL")
        observe_context(
            teacher, capability="C.ADD", phase="RECOVERY_2",
            policy_key="retained", decision=retained, local_gain=.4,
            curriculum_scope="scope")

        class Legacy:
            @staticmethod
            def pick(_teacher, _grade, _rng):
                return "legacy", _teacher["strategies"]["legacy"]

        picked, _ = contextual_pick(
            Legacy, teacher, "C.ADD", "RECOVERY_2", random.Random(2),
            curriculum_scope="scope")
        self.assertEqual(picked, "retained")

    def test_capability_stagnation_spans_policy_ids_and_suppresses_novelty(self):
        teacher = {
            "strategies": {
                "winner": {"lr": .00008},
                "failed_a": {"lr": .0002},
                "failed_b": {"lr": .0003},
                "novel": {"lr": .00013},
            },
            "global_stats": {
                key: {"trials": 20, "reward_sum": 2., "reward_ema": .1,
                      "latest": .1}
                for key in ("winner", "failed_a", "failed_b", "novel")
            },
            "grade_stats": {},
            "events": 80,
        }
        retained = decide({
            "C.SUB": {"before": 18, "after": 22, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_2", protected=set(),
            settings=Settings())
        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_2",
            policy_key="winner", decision=retained, local_gain=.4,
            curriculum_scope="scope")

        no_gain = decide({
            "C.SUB": {"before": 22, "after": 22, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_2", protected=set(),
            settings=Settings())
        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_2",
            policy_key="failed_a", decision=no_gain, local_gain=0.,
            curriculum_scope="scope")
        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_1",
            policy_key="failed_b", decision=dict(no_gain, phase="RECOVERY_1"),
            local_gain=0., curriculum_scope="scope")

        capability = teacher["causal_experiment"]["capability_stagnation"][
            "C.SUB|scope"]
        self.assertEqual(capability["rejection_streak"], 2)
        self.assertEqual(capability["no_target_gain_streak"], 2)
        self.assertEqual(capability["attempts_since_retained"], 2)

        class Legacy:
            @staticmethod
            def pick(_teacher, _grade, _rng):
                return "novel", _teacher["strategies"]["novel"]

        picked, _ = contextual_pick(
            Legacy, teacher, "C.SUB", "RECOVERY_2", random.Random(2),
            curriculum_scope="scope")
        self.assertEqual(picked, "winner")

    def test_preview_only_variants_share_effective_context_evidence(self):
        common = {
            "contrast": .5, "depth": 2, "distill": .15,
            "lr": .00008, "old": 12,
        }
        teacher = {
            "strategies": {
                "preview0": {**common, "preview": 0},
                "preview4": {**common, "preview": 4},
                "legacy": {
                    "contrast": 1., "depth": 4, "distill": .65,
                    "lr": .0003, "old": 4, "preview": 2,
                },
            },
            "global_stats": {
                key: {"trials": 20, "reward_sum": 0., "reward_ema": 0.,
                      "latest": 0.}
                for key in ("preview0", "preview4", "legacy")
            },
            "grade_stats": {},
            "events": 60,
        }
        mild_reject = decide({
            "C.SUB": {"before": 22, "after": 22, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_2", protected=set(),
            settings=Settings())
        for key in ("preview0", "preview4"):
            observe_context(
                teacher, capability="C.SUB", phase="RECOVERY_2",
                policy_key=key, decision=mild_reject, local_gain=0.,
                curriculum_scope="scope")

        worse_reject = decide({
            "C.SUB": {"before": 22, "after": 18, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_2", protected=set(),
            settings=Settings())
        for _ in range(2):
            observe_context(
                teacher, capability="C.SUB", phase="RECOVERY_2",
                policy_key="legacy", decision=worse_reject, local_gain=-.4,
                curriculum_scope="scope")

        class Legacy:
            @staticmethod
            def pick(_teacher, _grade, _rng):
                return "legacy", _teacher["strategies"]["legacy"]

        picked, _ = contextual_pick(
            Legacy, teacher, "C.SUB", "RECOVERY_2", random.Random(2),
            curriculum_scope="scope")
        self.assertIn(picked, {"preview0", "preview4"})

    def test_policy_identity_collapses_behavioral_depth_and_contrast_aliases(self):
        shallow_a = {
            "contrast": .5, "depth": 1, "distill": .15,
            "lr": .00008, "old": 12, "preview": 0,
        }
        shallow_b = {
            "contrast": 1., "depth": 2, "distill": .15,
            "lr": .00008, "old": 12, "preview": 4,
        }
        deep = {**shallow_a, "depth": 3}
        random_contrast = {**shallow_a, "contrast": 0.}
        self.assertEqual(
            _effective_policy_key(shallow_a),
            _effective_policy_key(shallow_b))
        self.assertNotEqual(
            _effective_policy_key(shallow_a),
            _effective_policy_key(deep))
        self.assertNotEqual(
            _effective_policy_key(shallow_a),
            _effective_policy_key(random_contrast))

    def test_active_strategy_population_is_bounded_and_preserves_proven_incumbent(self):
        teacher = strategy_population_teacher()
        proven = "policy-023"
        retained = decide({
            "C.ADD": {"before": 3, "after": 5, "total": 6},
        }, active_capability="C.ADD", phase="MAIN", protected=set(),
            settings=Settings())
        for _ in range(5):
            observe_context(
                teacher, capability="C.ADD", phase="MAIN",
                policy_key=proven, decision=retained, local_gain=.4,
                curriculum_scope="scope")
        scope = teacher["causal_experiment"]["contexts"]["C.ADD|MAIN|scope"]

        active, inventory = _active_effective_strategy_keys(
            teacher, "C", scope)

        self.assertLessEqual(len(active), 16)
        self.assertGreater(len(inventory), len(active))
        self.assertIn(
            _effective_policy_key(teacher["strategies"][proven]), active)

    def test_contextual_pick_keeps_strategy_archive_immutable(self):
        import bilqis_mlx.compatibility.historical_teacher_policy as policy_engine
        teacher = strategy_population_teacher()
        before_keys = set(teacher["strategies"])
        before_mutations = teacher["mutations"]

        for seed in range(12):
            contextual_pick(
                policy_engine, teacher, "C.ADD", "MAIN", random.Random(seed),
                curriculum_scope="scope")

        self.assertEqual(set(teacher["strategies"]), before_keys)
        self.assertEqual(teacher["mutations"], before_mutations)

    def test_zero_retention_strategy_rotates_off_active_bench(self):
        teacher = strategy_population_teacher()
        active_before, inventory = _active_effective_strategy_keys(
            teacher, "C", {})
        no_gain = decide({
            "C.ADD": {"before": 3, "after": 3, "total": 6},
        }, active_capability="C.ADD", phase="MAIN", protected=set(),
            settings=Settings())
        for effective_key in active_before:
            member = inventory[effective_key][0]
            observe_context(
                teacher, capability="C.ADD", phase="MAIN",
                policy_key=member, decision=no_gain, local_gain=0.,
                curriculum_scope="scope")
        scope = teacher["causal_experiment"]["contexts"]["C.ADD|MAIN|scope"]

        active_after, _ = _active_effective_strategy_keys(
            teacher, "C", scope)

        self.assertNotEqual(set(active_before), set(active_after))
        self.assertTrue(set(active_after) - set(active_before))

    def test_candidate_step_budget_shrinks_only_for_interference_pressure(self):
        teacher = {
            "strategies": {"policy": {"lr": .00013}},
            "global_stats": {
                "policy": {"trials": 20, "reward_sum": 0.,
                           "reward_ema": 0., "latest": 0.},
            },
            "grade_stats": {},
            "events": 20,
        }
        self.assertEqual(
            candidate_step_budget(
                16, teacher, "C.SUB", curriculum_scope="scope"), 16)

        no_gain = decide({
            "C.SUB": {"before": 22, "after": 22, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_1", protected=set(),
            settings=Settings())
        for _ in range(4):
            observe_context(
                teacher, capability="C.SUB", phase="RECOVERY_1",
                policy_key="policy", decision=no_gain, local_gain=0.,
                curriculum_scope="scope")
        self.assertEqual(
            candidate_step_budget(
                16, teacher, "C.SUB", curriculum_scope="scope"), 16)

        interference = decide({
            "C.SUB": {"before": 22, "after": 23, "total": 33},
            "A.EDGE": {"before": 6, "after": 4, "total": 6},
        }, active_capability="C.SUB", phase="RECOVERY_1",
            protected={"A.EDGE"}, settings=Settings())
        for _ in range(2):
            observe_context(
                teacher, capability="C.SUB", phase="RECOVERY_1",
                policy_key="policy", decision=interference, local_gain=.03,
                curriculum_scope="scope")
        self.assertEqual(
            candidate_step_budget(
                16, teacher, "C.SUB", curriculum_scope="scope"), 8)
        for _ in range(2):
            observe_context(
                teacher, capability="C.SUB", phase="RECOVERY_1",
                policy_key="policy", decision=interference, local_gain=.03,
                curriculum_scope="scope")
        self.assertEqual(
            candidate_step_budget(
                16, teacher, "C.SUB", curriculum_scope="scope"), 4)

        retained = decide({
            "C.SUB": {"before": 22, "after": 23, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_1", protected=set(),
            settings=Settings())
        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_1",
            policy_key="policy", decision=retained, local_gain=.03,
            curriculum_scope="scope")
        self.assertEqual(
            candidate_step_budget(
                16, teacher, "C.SUB", curriculum_scope="scope"), 16)

    def test_candidate_step_budget_recovers_when_interference_streak_breaks(self):
        teacher = {
            "strategies": {"policy": {"lr": .00013}},
            "global_stats": {
                "policy": {"trials": 20, "reward_sum": 0.,
                           "reward_ema": 0., "latest": 0.},
            },
            "grade_stats": {},
            "events": 20,
        }
        interference = decide({
            "C.SUB": {"before": 22, "after": 23, "total": 33},
            "A.EDGE": {"before": 6, "after": 4, "total": 6},
        }, active_capability="C.SUB", phase="RECOVERY_1",
            protected={"A.EDGE"}, settings=Settings())
        no_gain = decide({
            "C.SUB": {"before": 22, "after": 22, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_1", protected=set(),
            settings=Settings())

        for _ in range(4):
            observe_context(
                teacher, capability="C.SUB", phase="RECOVERY_1",
                policy_key="policy", decision=interference, local_gain=.03,
                curriculum_scope="scope")
        self.assertEqual(
            candidate_step_budget(
                16, teacher, "C.SUB", curriculum_scope="scope"), 4)

        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_1",
            policy_key="policy", decision=no_gain, local_gain=0.,
            curriculum_scope="scope")
        self.assertEqual(
            candidate_step_budget(
                16, teacher, "C.SUB", curriculum_scope="scope"), 16)

    def test_legacy_accumulated_interference_does_not_throttle_new_runtime(self):
        teacher = {
            "causal_experiment": {
                "version": "bilqis.mlx.causal-teacher-experiment/v1",
                "contexts": {}, "negative_archetypes": [], "events": 0,
                "capability_stagnation": {
                    "C.SUB|scope": {
                        "rejection_streak": 40,
                        "no_target_gain_streak": 5,
                        "attempts_since_retained": 40,
                        "total_rejections": 100,
                        "total_retained": 2,
                        "current_rejection_reasons": {
                            "ACTIVE_SCHOOL_GRADE_REGRESSION": 8,
                            "NO_MEASURABLE_TARGET_GAIN": 32,
                        },
                    },
                },
            },
        }
        self.assertEqual(
            candidate_step_budget(
                16, teacher, "C.SUB", curriculum_scope="scope"), 16)

    def test_geometry_context_does_not_delegate_first_pick_to_legacy_bandit(self):
        teacher = {
            "strategies": {
                "a": {"lr": .00008, "old": 8, "preview": 0,
                      "depth": 1, "contrast": 0., "distill": 0.},
                "b": {"lr": .00013, "old": 12, "preview": 2,
                      "depth": 3, "contrast": .5, "distill": .15},
            },
            "global_stats": {
                "a": {"trials": 100, "reward_sum": -20.,
                      "reward_ema": -.2, "latest": -.2},
                "b": {"trials": 100, "reward_sum": 20.,
                      "reward_ema": .2, "latest": .2},
            },
            "grade_stats": {"B": {
                "a": {"trials": 100, "reward_sum": -20.,
                      "reward_ema": -.2, "latest": -.2},
                "b": {"trials": 100, "reward_sum": 20.,
                      "reward_ema": .2, "latest": .2},
            }},
            "events": 200,
        }

        class Legacy:
            calls = 0

            @classmethod
            def pick(cls, _teacher, _grade, _rng):
                cls.calls += 1
                return "a", _teacher["strategies"]["a"]

        picked, policy = contextual_pick(
            Legacy, teacher, "B.AND", "MAIN", random.Random(7),
            curriculum_scope="scope/geometry=outer-v1")
        self.assertIn(picked, teacher["strategies"])
        self.assertEqual(policy, teacher["strategies"][picked])
        self.assertEqual(Legacy.calls, 0)
        no_gain = decide({
            "B.AND": {"before": 6, "after": 6, "total": 12},
        }, active_capability="B.AND", phase="MAIN", protected=set(),
            settings=Settings())
        credit = observe_context(
            teacher, capability="B.AND", phase="MAIN",
            policy_key=picked, decision=no_gain, local_gain=0.,
            curriculum_scope="scope/geometry=outer-v1")
        self.assertEqual(credit["inherited_exploration_credit"], 0.)

    def test_geometry_local_outcome_outweighs_historical_policy_ranking(self):
        common = {"old": 8, "preview": 0, "depth": 1,
                  "contrast": 0., "distill": 0.}
        teacher = {
            "strategies": {
                "historical_winner": {**common, "lr": .0003},
                "geometry_winner": {**common, "lr": .00008},
            },
            "global_stats": {
                "historical_winner": {"trials": 100, "reward_sum": 80.,
                                      "reward_ema": .8, "latest": .8},
                "geometry_winner": {"trials": 100, "reward_sum": -80.,
                                    "reward_ema": -.8, "latest": -.8},
            },
            "grade_stats": {"B": {
                "historical_winner": {"trials": 100, "reward_sum": 80.,
                                      "reward_ema": .8, "latest": .8},
                "geometry_winner": {"trials": 100, "reward_sum": -80.,
                                    "reward_ema": -.8, "latest": -.8},
            }},
            "events": 200,
            "causal_experiment": {
                "version": "bilqis.mlx.causal-teacher-experiment/v1",
                "negative_archetypes": [], "events": 1,
                "contexts": {
                    "B.AND|MAIN|scope/geometry=outer-v1": {
                        "geometry_winner": {
                            "trials": 1, "reward_sum": .5,
                            "unsafe": 0, "retained": 1,
                            "latest": .5, "no_target_gain_streak": 0,
                        },
                    },
                },
            },
        }

        class Legacy:
            @staticmethod
            def pick(_teacher, _grade, _rng):
                return "historical_winner", _teacher["strategies"]["historical_winner"]

        picked, _ = contextual_pick(
            Legacy, teacher, "B.AND", "MAIN", random.Random(3),
            curriculum_scope="scope/geometry=outer-v1")
        self.assertEqual(picked, "geometry_winner")

    def test_rejection_pressure_stops_unseen_legacy_novelty_without_retained_winner(self):
        teacher = {
            "strategies": {
                "less_bad": {"lr": .00008},
                "worse": {"lr": .0002},
                "novel": {"lr": .00013},
            },
            "global_stats": {
                key: {"trials": 20, "reward_sum": 0., "reward_ema": 0.,
                      "latest": 0.}
                for key in ("less_bad", "worse", "novel")
            },
            "grade_stats": {},
            "events": 60,
        }
        mild_reject = decide({
            "C.SUB": {"before": 22, "after": 22, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_1", protected=set(),
            settings=Settings())
        worse_reject = decide({
            "C.SUB": {"before": 22, "after": 18, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_1", protected=set(),
            settings=Settings())
        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_1",
            policy_key="less_bad", decision=mild_reject, local_gain=0.,
            curriculum_scope="scope")
        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_1",
            policy_key="worse", decision=worse_reject, local_gain=-.4,
            curriculum_scope="scope")

        class Legacy:
            calls = 0

            @staticmethod
            def pick(_teacher, _grade, _rng):
                Legacy.calls += 1
                return "novel", _teacher["strategies"]["novel"]

        picked, _ = contextual_pick(
            Legacy, teacher, "C.SUB", "RECOVERY_1", random.Random(2),
            curriculum_scope="scope")
        self.assertEqual(picked, "less_bad")
        self.assertEqual(Legacy.calls, 0)

        stagnation = teacher["causal_experiment"]["capability_stagnation"][
            "C.SUB|scope"]
        stagnation["rejection_streak"] = 4
        stagnation["attempts_since_retained"] = 4
        picked, _ = contextual_pick(
            Legacy, teacher, "C.SUB", "RECOVERY_1", random.Random(2),
            curriculum_scope="scope")
        self.assertEqual(picked, "novel")
        self.assertEqual(Legacy.calls, 1)

    def test_rejection_pressure_pools_learning_rate_evidence_across_phases(self):
        teacher = {
            "strategies": {
                "low": {
                    "contrast": .5, "depth": 2, "distill": .15,
                    "lr": .00008, "old": 12, "preview": 0,
                },
                "high": {
                    "contrast": .5, "depth": 2, "distill": .15,
                    "lr": .0003, "old": 12, "preview": 0,
                },
            },
            "global_stats": {
                key: {"trials": 20, "reward_sum": 0., "reward_ema": 0.,
                      "latest": 0.}
                for key in ("low", "high")
            },
            "grade_stats": {},
            "events": 80,
            "causal_experiment": {
                "version": "bilqis.mlx.causal-teacher-experiment/v1",
                "contexts": {
                    "C.SUB|MAIN|scope": {
                        "low": {
                            "trials": 4, "reward_sum": 2.,
                            "unsafe": 0, "retained": 4,
                            "latest": .5, "no_target_gain_streak": 0,
                        },
                        "high": {
                            "trials": 4, "reward_sum": -2.,
                            "unsafe": 4, "retained": 0,
                            "latest": -.5, "no_target_gain_streak": 4,
                        },
                    },
                    "C.SUB|RECOVERY_2|scope": {
                        "low": {
                            "trials": 2, "reward_sum": .1,
                            "unsafe": 1, "retained": 1,
                            "latest": .05, "no_target_gain_streak": 0,
                        },
                        "high": {
                            "trials": 2, "reward_sum": .2,
                            "unsafe": 1, "retained": 1,
                            "latest": .1, "no_target_gain_streak": 0,
                        },
                    },
                },
                "capability_stagnation": {
                    "C.SUB|scope": {
                        "rejection_streak": 6,
                        "no_target_gain_streak": 3,
                        "attempts_since_retained": 6,
                        "total_rejections": 8,
                        "total_retained": 2,
                    },
                },
            },
        }

        class Legacy:
            @staticmethod
            def pick(_teacher, _grade, _rng):
                return "high", _teacher["strategies"]["high"]

        picked, _ = contextual_pick(
            Legacy, teacher, "C.SUB", "RECOVERY_2", random.Random(2),
            curriculum_scope="scope")
        self.assertEqual(picked, "low")

    def test_diagnostic_context_prefers_policy_proven_under_current_signal(self):
        teacher = {
            "strategies": {
                "diagnostic": {"lr": .00008},
                "legacy": {"lr": .00013},
            },
            "global_stats": {
                key: {"trials": 20, "reward_sum": 0., "reward_ema": 0.,
                      "latest": 0.}
                for key in ("diagnostic", "legacy")
            },
            "grade_stats": {},
            "events": 40,
        }
        retained = decide({
            "C.SUB": {"before": 20, "after": 22, "total": 33},
        }, active_capability="C.SUB", phase="RECOVERY_2", protected=set(),
            settings=Settings())
        matching = {
            "warnings": ("CHANCE_LEVEL_OR_LAGGING",),
            "unresolved_miss_count": 12,
            "champion_candidate_count": 3,
        }
        other = {
            "warnings": (),
            "unresolved_miss_count": 0,
            "champion_candidate_count": 0,
        }
        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_2",
            policy_key="diagnostic", decision=retained, local_gain=.2,
            curriculum_scope="scope", diagnostics=matching)
        observe_context(
            teacher, capability="C.SUB", phase="RECOVERY_2",
            policy_key="legacy", decision=retained, local_gain=.8,
            curriculum_scope="scope", diagnostics=other)

        class Legacy:
            @staticmethod
            def pick(_teacher, _grade, _rng):
                return "legacy", _teacher["strategies"]["legacy"]

        picked, _policy, selection = contextual_pick(
            Legacy, teacher, "C.SUB", "RECOVERY_2", random.Random(2),
            curriculum_scope="scope", diagnostics=matching,
            return_metadata=True)
        self.assertEqual(picked, "diagnostic")
        self.assertTrue(selection["diagnostic_context_consumed"])
        self.assertIsInstance(selection["diagnostic_context_key"], str)

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
            protected_frontier_grade="C")
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
            protected_frontier_grade="C")
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
