"""Candidate evidence."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, Settings, decide, patch,
    schedule_program,
)


class CandidateEvidence2Tests(CausalTeacherExperimentTests):
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
