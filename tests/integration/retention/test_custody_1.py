"""Retention integration contracts; original evidence and boundaries preserved."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from bilqis_mlx import trainer as trainer
from bilqis_mlx.learning.learning_experiment import Settings
from bilqis_mlx.runtime import visits as runtime_visits
from tests.integration.retention.fixtures import VisitFixture, _BatchCaptured, _rows, _visit_program, _visit_release


class CustodyTests(VisitFixture, unittest.TestCase):
    def test_retention_support_tracks_frontier_or_same_grade_peers(self):
        admitted = (
            "A.IDENTITY", "B.AND", "B.IFF",
            "C.COUNT", "C.NUMBER", "C.SUCCESSOR", "C.ADD", "C.SUB")
        self.assertEqual(
            runtime_visits._runtime_candidate_evidence._retention_support_capabilities(
                admitted, ("A", "B", "C"), "B.AND"),
            ("C.ADD", "C.COUNT", "C.NUMBER", "C.SUB", "C.SUCCESSOR"),
        )
        self.assertEqual(
            runtime_visits._runtime_candidate_evidence._retention_support_capabilities(
                admitted, ("A", "B", "C"), "C.SUB"),
            ("C.ADD", "C.COUNT", "C.NUMBER", "C.SUCCESSOR"),
        )

    def test_b_debt_visit_delivers_fresh_c_frontier_support(self):
        policy = {"old": 0, "lr": 0.0001, "depth": 1,
                  "contrast": 1., "distill": 0., "preview": 0}
        teacher = {"strategies": {"p": policy}}
        engine = SimpleNamespace(pick=lambda *_: ("p", policy))
        school = SimpleNamespace(
            schema="bilqis.mlx.letter-grade/v1",
            stage="MAIN", grade="B", visits=4,
            active_grades=("A", "B", "C"),
            champions={"A": {"optimizer_step": 1}},
            carried_mastery_debt=("B.XOR", "C.COUNT"),
        )
        course = _visit_program()
        receipt = {
            "teacher": teacher, "generation": 1, "run_id": "frontier-support",
            "school": {}, "teacher_misses": [], "config": {},
            "answer_ids": [6, 7], "curriculum_mode": "fixture-school",
        }
        optimizer = SimpleNamespace(
            learning_rate=0.0001,
            state={"step": SimpleNamespace(item=lambda: 1)})
        captured = []

        def source_rows(*_args, **kwargs):
            return _rows(kwargs["capability"])

        def inspect_batch(_mx, _parameters, _optimizer, rows, *_args, **_kwargs):
            captured.extend(rows)
            raise _BatchCaptured("FRONTIER_SUPPORT_CAPTURED")

        def wrong_predictions(_mx, _params, rows, *_args):
            return {row["id"]: ("FALSE" if row["gold"] == "TRUE" else "TRUE")
                    for row in rows}

        with (patch('bilqis_mlx.runtime.state._state_from_json', return_value=school),
              patch('bilqis_mlx.runtime.admission._read_executable_factory_release_artifact',
                    return_value=_visit_release(course)),
              patch('bilqis_mlx.factory.schedule.schedule_program_from_executable_release',
                    return_value=course),
              patch('bilqis_mlx.curriculum.scheduler.next_capability', return_value="B.XOR"),
              patch('bilqis_mlx.curriculum.scheduler.assessment_capabilities',
                    return_value=("A.IDENTITY", "B.XOR", "C.COUNT")),
              patch('bilqis_mlx.runtime.assessment._draw_live_rows',
                    side_effect=source_rows),
              patch('bilqis_mlx.learning.lesson_guidance._frozen_confidence_champions',
                    return_value=()),
              patch('bilqis_mlx.learning.lesson_guidance._frozen_grade_soup_votes',
                    return_value=((), ())),
              patch('bilqis_mlx.learning.student_ops._train_score', return_value=0.5),
              patch('bilqis_mlx.runtime.candidate_evidence._learning_probe_rows',
                    return_value=(_rows("B.XOR")[:6], set(), 0)),
              patch('bilqis_mlx.learning.student_ops._predictions',
                    side_effect=wrong_predictions),
              patch('bilqis_mlx.learning.learning_experiment.fork_student',
                    return_value=({}, optimizer)),
              patch('bilqis_mlx.diagnostics.teaching.inspect_lesson_step',
                    side_effect=ValueError("fixture methodology unavailable")),
              patch("bilqis_mlx.learning.fragile_replay.load_replay_rows",
                    return_value=()),
              patch('bilqis_mlx.learning.student_ops._train_step',
                    side_effect=inspect_batch)):
            with self.assertRaisesRegex(_BatchCaptured, "FRONTIER_SUPPORT_CAPTURED"):
                trainer._take_visit(
                    None, Path("/never-opened"), receipt, {}, course, engine,
                    {}, optimizer, {}, steps_per_visit=1, batch_size=8,
                    reserve_gib=0., source_root=Path("/not-used"),
                    learning_settings=Settings())

        self.assertIn("C.COUNT", {row["capability"] for row in captured})
        self.assertIn("B.XOR", {row["capability"] for row in captured})

    def test_rejected_candidate_preserves_teacher_exposure_history(self):
        receipt = {"teacher_miss_exposures": {
            "weak:a": 2,
            "weak:b": 0,
        }}
        attempted = {
            "weak:a": 3,
            "weak:b": 1,
        }
        self.assertEqual(
            runtime_visits._teacher_exposures_after_candidate(
                receipt, attempted, decision="REJECT"),
            attempted,
        )

    def test_binary_grade_b_visit_does_not_invent_old_examples_at_zero_policy(self):
        self.assertEqual(set(self._visit_selection(old=0)), {"B.XOR"})
