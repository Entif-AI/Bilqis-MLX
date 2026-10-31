"""Retention integration contracts; original evidence and boundaries preserved."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from bilqis_mlx import trainer as trainer
from bilqis_mlx.learning.learning_experiment import Settings
from tests.integration.retention.fixtures import VisitFixture, _BatchCaptured, _rows, _visit_program, _visit_release


class CustodyTests(VisitFixture, unittest.TestCase):
    def test_fragile_preservation_shares_batch_capacity_with_weakness_targets(self):
        policy = {"old": 0, "lr": 0.0001, "depth": 1,
                  "contrast": 1., "distill": 0., "preview": 0}
        teacher = {"strategies": {"p": policy}}
        engine = SimpleNamespace(pick=lambda *_: ("p", policy))
        school = SimpleNamespace(stage="MAIN", grade="B", visits=0,
                                 champions={"A": {"optimizer_step": 1}})
        course = _visit_program()
        misses = [
            {"id": f"miss:{index}", "source_id": f"miss:{index}",
             "capability": "B.XOR", "answer_kind": "binary",
             "gold": "TRUE" if index % 2 else "FALSE",
             "tokens": [8, 9, index + 10]}
            for index in range(30)
        ]
        preservation = tuple(
            {"id": f"preserve:{index}", "capability": "B.XOR",
             "answer_kind": "binary",
             "gold": "TRUE" if index % 2 else "FALSE",
             "operand_truths": [bool(index & 1), bool(index & 2)],
             "tokens": [20, 21, index + 22]}
            for index in range(8)
        )
        receipt = {"teacher": teacher, "generation": 1, "run_id": "capacity",
                   "school": {}, "teacher_misses": misses, "config": {},
                   "answer_ids": [6, 7], "curriculum_mode": "fixture-school"}
        optimizer = SimpleNamespace(learning_rate=0.0001,
                                    state={"step": SimpleNamespace(item=lambda: 1)})
        captured = []

        def source_rows(*_args, **kwargs):
            return _rows(kwargs["capability"])

        def inspect_batch(_mx, _parameters, _optimizer, rows, *_args, **_kwargs):
            captured.extend(rows)
            raise _BatchCaptured("STOP_BEFORE_ANY_OPTIMIZER")

        def wrong_predictions(_mx, _params, rows, *_args):
            return {row["id"]: ("FALSE" if row["gold"] == "TRUE" else "TRUE")
                    for row in rows}

        with (patch('bilqis_mlx.runtime.state._state_from_json', return_value=school),
              patch('bilqis_mlx.runtime.admission._read_executable_factory_release_artifact',
                           return_value=_visit_release(course)),
              patch('bilqis_mlx.factory.schedule.schedule_program_from_executable_release',
                           return_value=course),
              patch('bilqis_mlx.curriculum.scheduler.next_capability', return_value="B.XOR"),
              patch('bilqis_mlx.runtime.assessment._draw_live_rows', side_effect=source_rows),
              patch('bilqis_mlx.learning.lesson_guidance._frozen_confidence_champions', return_value=()),
              patch('bilqis_mlx.learning.lesson_guidance._frozen_grade_soup_votes', return_value=((), ())),
              patch('bilqis_mlx.learning.student_ops._train_score', return_value=0.5),
              patch('bilqis_mlx.runtime.candidate_evidence._learning_probe_rows',
                           return_value=(_rows("B.XOR")[:6], set(), 0)),
              patch('bilqis_mlx.learning.student_ops._predictions', side_effect=wrong_predictions),
              patch('bilqis_mlx.learning.learning_experiment.fork_student', return_value=({}, optimizer)),
              patch('bilqis_mlx.diagnostics.teaching.inspect_lesson_step',
                           side_effect=ValueError("fixture methodology unavailable")),
              patch("bilqis_mlx.learning.fragile_replay.load_replay_rows",
                    return_value=({"id": "fixed"},)),
              patch('bilqis_mlx.runtime.candidate_evidence._fresh_fragile_preservation_rows',
                           return_value=preservation),
              patch('bilqis_mlx.learning.student_ops._train_step', side_effect=inspect_batch)):
            with self.assertRaisesRegex(_BatchCaptured, "STOP_BEFORE_ANY_OPTIMIZER"):
                trainer._take_visit(None, Path("/never-opened"), receipt, {},
                                    course, engine, {}, optimizer, {},
                                    steps_per_visit=1, batch_size=32,
                                    reserve_gib=0., source_root=Path("/not-used"),
                                    learning_settings=Settings())

        self.assertEqual(len(captured), 32)
        self.assertEqual({row["id"] for row in preservation} &
                         {row["id"] for row in captured},
                         {row["id"] for row in preservation})
        delivered_misses = {row["id"] for row in captured if row["id"].startswith("miss:")}
        self.assertEqual(len(delivered_misses), 23)
        self.assertTrue(any(
            row["id"].startswith("B.XOR:") for row in captured),
            "A fresh current-capability row must survive miss replay and preservation")

    def test_fragile_preservation_reserves_batch_capacity_before_miss_replay(self):
        policy = {"old": 0, "lr": 0.0001, "depth": 1,
                  "contrast": 1., "distill": 0., "preview": 0}
        teacher = {"strategies": {"p": policy}}
        engine = SimpleNamespace(pick=lambda *_: ("p", policy))
        school = SimpleNamespace(stage="MAIN", grade="B", visits=0,
                                 champions={"A": {"optimizer_step": 1}})
        course = _visit_program()
        misses = [
            {"id": f"miss:{index}", "source_id": f"miss:{index}",
             "capability": "B.XOR", "answer_kind": "binary",
             "gold": "TRUE" if index % 2 else "FALSE",
             "tokens": [8, 9, index + 10]}
            for index in range(30)
        ]
        preservation = tuple(
            {"id": f"preserve:{index}", "capability": "B.XOR",
             "answer_kind": "binary",
             "gold": "TRUE" if index % 2 else "FALSE",
             "operand_truths": [bool(index & 1), bool(index & 2)],
             "tokens": [20, 21, index + 22]}
            for index in range(8)
        )
        receipt = {"teacher": teacher, "generation": 1, "run_id": "capacity",
                   "school": {}, "teacher_misses": misses, "config": {},
                   "answer_ids": [6, 7], "curriculum_mode": "fixture-school"}
        optimizer = SimpleNamespace(learning_rate=0.0001,
                                    state={"step": SimpleNamespace(item=lambda: 1)})
        captured = []

        def source_rows(*_args, **kwargs):
            return _rows(kwargs["capability"])

        def inspect_batch(_mx, _parameters, _optimizer, rows, *_args, **_kwargs):
            captured.extend(rows)
            raise _BatchCaptured("STOP_BEFORE_ANY_OPTIMIZER")

        def wrong_predictions(_mx, _params, rows, *_args):
            return {row["id"]: ("FALSE" if row["gold"] == "TRUE" else "TRUE")
                    for row in rows}

        with (patch('bilqis_mlx.runtime.state._state_from_json', return_value=school),
              patch('bilqis_mlx.runtime.admission._read_executable_factory_release_artifact',
                           return_value=_visit_release(course)),
              patch('bilqis_mlx.factory.schedule.schedule_program_from_executable_release',
                           return_value=course),
              patch('bilqis_mlx.curriculum.scheduler.next_capability', return_value="B.XOR"),
              patch('bilqis_mlx.runtime.assessment._draw_live_rows', side_effect=source_rows),
              patch('bilqis_mlx.learning.lesson_guidance._frozen_confidence_champions', return_value=()),
              patch('bilqis_mlx.learning.lesson_guidance._frozen_grade_soup_votes', return_value=((), ())),
              patch('bilqis_mlx.learning.student_ops._train_score', return_value=0.5),
              patch('bilqis_mlx.runtime.candidate_evidence._learning_probe_rows',
                           return_value=(_rows("B.XOR")[:6], set(), 0)),
              patch('bilqis_mlx.learning.student_ops._predictions', side_effect=wrong_predictions),
              patch('bilqis_mlx.learning.learning_experiment.fork_student', return_value=({}, optimizer)),
              patch('bilqis_mlx.diagnostics.teaching.inspect_lesson_step',
                           side_effect=ValueError("fixture methodology unavailable")),
              patch("bilqis_mlx.learning.fragile_replay.load_replay_rows",
                    return_value=({"id": "fixed"},)),
              patch('bilqis_mlx.runtime.candidate_evidence._fresh_fragile_preservation_rows',
                           return_value=preservation),
              patch('bilqis_mlx.learning.student_ops._train_step', side_effect=inspect_batch)):
            with self.assertRaisesRegex(_BatchCaptured, "STOP_BEFORE_ANY_OPTIMIZER"):
                trainer._take_visit(None, Path("/never-opened"), receipt, {},
                                    course, engine, {}, optimizer, {},
                                    steps_per_visit=1, batch_size=32,
                                    reserve_gib=0., source_root=Path("/not-used"),
                                    learning_settings=Settings())

        self.assertEqual(len(captured), 32)
        self.assertEqual({row["id"] for row in preservation} &
                         {row["id"] for row in captured},
                         {row["id"] for row in preservation})
        delivered_misses = {row["id"] for row in captured if row["id"].startswith("miss:")}
        self.assertEqual(len(delivered_misses), 23)
        self.assertTrue(any(
            row["id"].startswith("B.XOR:") for row in captured),
            "A fresh current-capability row must survive miss replay and preservation")
