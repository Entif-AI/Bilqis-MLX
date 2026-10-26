"""Read-only projections for Factory teacher-observation receipts."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from bilqis_mlx.factory.schedule import (
    ScheduleCapability, ScheduleGrade, ScheduleProgram,
)
from bilqis_mlx.learning.teacher_observations import (
    candidate_outcome, portable_v1_observation, student_region,
    summarize_observations,
)


def program():
    return ScheduleProgram(
        program_digest="a" * 64,
        grades=(
            ScheduleGrade("A", (ScheduleCapability("A.LINK", 12),), (), None),
            ScheduleGrade("B", (ScheduleCapability("B.AND", 12),), (), None),
            ScheduleGrade("C", (
                ScheduleCapability("C.COUNT", 33),
                ScheduleCapability("C.NUMBER", 33),
                ScheduleCapability("C.ADD", 33),
                ScheduleCapability("C.SUB", 33),
            ), (), None),
        ),
        program_complete=False,
    )


def receipt():
    return {
        "last_exam": {"scores": {
            "C.ADD": {"correct": 28, "total": 33},
            "C.COUNT": {"correct": 31, "total": 33},
            "C.SUB": {"correct": 22, "total": 33},
        }},
        "school": {"carried_mastery_debt": ("A.LINK", "B.AND", "C.SUB")},
    }


class TeacherObservationTests(unittest.TestCase):
    def test_region_uses_declared_program_grade_ownership_not_capability_prefix(self):
        odd_program = ScheduleProgram(
            program_digest="a" * 64,
            grades=(ScheduleGrade("FOUNDATION", (
                ScheduleCapability("unprefixed", 12),), (), None),),
            program_complete=False,
        )
        result = student_region(
            {"last_exam": {"scores": {"unprefixed": {"correct": 9, "total": 12}}}},
            odd_program, "unprefixed", "MAIN",
        )
        self.assertEqual(result["lesson_grade"], "FOUNDATION")
        self.assertNotIn("topology", result)
        self.assertNotIn("student_sha256", result)

    def test_partial_target_only_rejection_does_not_forge_protected_zero(self):
        result = candidate_outcome({
            "decision": "REJECT", "reason": "NO_POSITIVE_TARGET_GAIN",
            "active_probe_before": 4, "active_probe_after": 4,
            "active_probe_total": 6,
            "fixed_grade_replay": {"status": "NOT_MEASURED", "reason": "TARGET_DID_NOT_GAIN"},
            "fixed_frontier_replay": {"status": "NOT_MEASURED", "reason": "TARGET_DID_NOT_GAIN"},
        }, paired={"C.ADD": {"before": 4, "after": 4, "total": 6}}, protected=(),
           stage="TARGET_ONLY_REJECTED", attempted_steps=8, retained_steps=0,
           wall_seconds=1.25)
        self.assertEqual(result["retention"]["value"], "REJECTED")
        self.assertEqual(result["target"]["after"], {"status": "MEASURED", "value": 4})
        self.assertEqual(result["protected"]["net_correct_delta"]["status"], "NOT_MEASURED")
        self.assertEqual(result["fixed_grade"]["status"], "NOT_MEASURED")

    def test_direct_teaching_keeps_retention_and_target_not_measured(self):
        result = candidate_outcome(None, stage="ORDINARY", attempted_steps=1,
                                   retained_steps=1, wall_seconds=0.0)
        self.assertEqual(result["retention"]["status"], "NOT_MEASURED")
        self.assertEqual(result["target"]["before"]["status"], "NOT_MEASURED")

    def test_fully_measured_fixture_bridges_to_unchanged_portable_v1(self):
        fixture_path = Path(__file__).parents[1] / "fixtures" / "teacher_vnext_conformance_v1.json"
        fixture = json.loads(fixture_path.read_text())
        region = student_region({"last_exam": {"scores": {
            key: {"correct": pair[0], "total": pair[1]}
            for key, pair in fixture["region"]["grade_capability_scores"].items()
        }}, "school": {"carried_mastery_debt": tuple(fixture["region"]["mastery_debt_capabilities"])}},
            program(), "C.ADD", "RECOVERY_1",
            teacher={"causal_experiment": {"capability_stagnation": {
                "C.ADD|fixture/scope": {"rejection_streak": 5,
                                        "attempts_since_retained": 7}}}},
            curriculum_scope=fixture["region"]["curriculum_scope"],
            geometry_epoch=fixture["region"]["geometry_epoch"],
            numeric_maximum=fixture["region"]["numeric_maximum"],
            grade_correct=fixture["region"]["grade_correct"],
            grade_total=fixture["region"]["grade_total"],
            grade_capability_scores=fixture["region"]["grade_capability_scores"])
        portable = portable_v1_observation(region, fixture["action"], candidate_outcome(
            {"decision": "PROVISIONAL", "reason": fixture["outcome"]["rejection_reason"],
             "active_probe_before": 4, "active_probe_after": 6, "active_probe_total": 8,
             "protected_net_correct_delta": 0, "worst_protected_loss": 0},
            paired={"C.ADD": {"before": 4, "after": 6, "total": 8},
                    "B.AND": {"before": 3, "after": 3, "total": 8}}, protected={"B.AND"},
            stage="RETAINED", attempted_steps=8, retained_steps=8, wall_seconds=1.5),
        )
        self.assertEqual(portable["retained"], True)
        self.assertEqual(portable["target_delta"], 2)
        self.assertEqual(portable["protected_net_delta"], 0)
        for key, expected in fixture["expected"].items():
            if key in region:
                self.assertEqual(region[key], expected)
        self.assertEqual(portable["region"]["schema"], "bilqis.teacher-student-region/v1")
        self.assertTrue(portable["proposed_action"]["key"])

    def test_summary_preserves_unmeasured_calibration_and_shadow(self):
        summary = summarize_observations((candidate_outcome(
            None, stage="ORDINARY", attempted_steps=1, retained_steps=1, wall_seconds=0),))
        self.assertEqual(summary["calibration"]["status"], "NOT_MEASURED")
        self.assertEqual(summary["shadow_probes"]["status"], "NOT_MEASURED")
        self.assertEqual(summary["coverage"]["optimizer_rows"]["status"], "NOT_MEASURED")

    def test_summary_counts_expanded_zero_step_skip_and_durable_acceptance_separately(self):
        accepted = candidate_outcome(
            {"decision": "PROVISIONAL", "reason": "PAIRED_SCREEN_WITHIN_BUDGET",
             "active_probe_before": 4, "active_probe_after": 5, "active_probe_total": 6,
             "worst_protected_loss": 0}, paired={"C.ADD": {"before": 4, "after": 5, "total": 6}},
            protected=(), stage="COMPLETE_SAME_GRADE", attempted_steps=3,
            retained_steps=2, wall_seconds=1.5)
        summary = summarize_observations((
            {"outcome": accepted, "publication": {"status": "DURABLE_CHECKPOINT_OUTBOX"},
             "proposal": {"phase": "MAIN", "student_region": {
                 "lesson_grade": "C", "mastery_debt_shape": "A:1"}},
             "steps": [{"delivered_teaching": {"option_id": "source.direct/C.ADD"},
                        "positions": [{"row": {"id": "one"}, "roles": ["constructed_target"]},
                                      {"row": {"id": "two"}, "roles": ["retention_support"]}]}]},
            {"outcome": candidate_outcome(None, stage="PERFECT_TARGET_SKIP", attempted_steps=0,
                                           retained_steps=0, wall_seconds=0),
             "proposal": {"phase": "MAIN", "student_region": {
                 "lesson_grade": "C", "mastery_debt_shape": "A:1"}}, "steps": []},
        ))
        self.assertEqual(summary["coverage"]["optimizer_rows"]["value"], 2)
        self.assertEqual(summary["coverage"]["roles"]["value"]["retention_support"], 1)
        self.assertEqual(summary["retention"]["provisional_accepted_attempts"]["value"], 1)
        self.assertEqual(summary["retention"]["durable_accepted_attempts"]["value"], 1)
        self.assertEqual(summary["scheduling"]["value"]["lesson_grades"]["C"], 2)


class MissingScopeTests(unittest.TestCase):
    def test_empty_protected_scope_is_unmeasured_even_if_decision_reports_zero(self):
        value = candidate_outcome({"decision": "PROVISIONAL", "reason": "PAIRED_SCREEN_WITHIN_BUDGET",
            "active_probe_before": 1, "active_probe_after": 2, "active_probe_total": 6,
            "worst_protected_loss": 0}, paired={"target": {"before": 1, "after": 2, "total": 6}},
            protected=(), stage="COMPLETE_SAME_GRADE", attempted_steps=1, retained_steps=1, wall_seconds=0.)
        self.assertEqual(value["protected"]["scope"]["status"], "NOT_MEASURED")
        self.assertEqual(value["worst_protected_loss"]["status"], "NOT_MEASURED")

    def test_partial_grade_score_is_not_a_complete_grade_band(self):
        value = student_region({"last_exam": {"scores": {"C.ADD": {"correct": 6, "total": 6}}}},
                               program(), "C.ADD", "MAIN")
        self.assertEqual(value["capability_score_band"], "P100")
        self.assertEqual(value["grade_score_band"], "UNMEASURED")

    def test_pressure_uses_current_scope_and_undefined_ratio_is_not_zero(self):
        teacher = {"causal_experiment": {"capability_stagnation": {"C.ADD|old": {"rejection_streak": 31}}}}
        value = student_region(receipt(), program(), "C.ADD", "MAIN", teacher, curriculum_scope="new")
        self.assertEqual(value["rejection_pressure_band"], "R00")
        summary = summarize_observations([])
        self.assertEqual(summary["seconds_per_provisional_retention"]["status"], "NOT_MEASURED")
        self.assertEqual(summary["seconds_per_durable_retention"]["status"], "NOT_MEASURED")
