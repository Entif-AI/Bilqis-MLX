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
    _diagnostic_context,
)
from bilqis_mlx.learning.teacher_strategy_population import effective_policy_features


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
    def setUp(self):
        self.rows = rows()
        self.before = predicted(self.rows, {"C.ADD0", "C.ADD1", "C.ADD2"})
