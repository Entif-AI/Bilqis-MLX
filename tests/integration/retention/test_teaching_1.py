"""Retention integration contracts; original evidence and boundaries preserved."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from bilqis_mlx import trainer as trainer
from bilqis_mlx.learning.learning_experiment import Settings
from bilqis_mlx.runtime import visits as runtime_visits
from tests.integration.retention.fixtures import VisitFixture, _BatchCaptured, _InlinePrefetchExecutor, _prefetch_visit_fixture, _rows, _visit_program, _visit_release


class TeachingTests(VisitFixture, unittest.TestCase):
    def test_retention_support_selects_one_complete_fresh_source_family(self):
        rows = [
            {"id": "a:n", "source_id": "a", "capability": "C.COUNT",
             "answer_kind": "numeric_active", "gold": "2"},
            {"id": "a:t", "source_id": "a", "capability": "C.COUNT",
             "answer_kind": "binary", "gold": "TRUE"},
            {"id": "a:f", "source_id": "a", "capability": "C.COUNT",
             "answer_kind": "binary", "gold": "FALSE"},
            {"id": "b:n", "source_id": "b", "capability": "C.COUNT",
             "answer_kind": "numeric_active", "gold": "3"},
            {"id": "b:t", "source_id": "b", "capability": "C.COUNT",
             "answer_kind": "binary", "gold": "TRUE"},
            {"id": "b:f", "source_id": "b", "capability": "C.COUNT",
             "answer_kind": "binary", "gold": "FALSE"},
        ]
        selected = (
            runtime_visits._runtime_candidate_evidence.
            _select_fresh_retention_support_rows(rows, rotation=1))
        self.assertEqual({row["source_id"] for row in selected}, {"b"})
        self.assertEqual({row["id"] for row in selected},
                         {"b:n", "b:t", "b:f"})

    def test_teacher_reward_scores_fresh_source_rows_not_exact_miss_replay(self):
        policy = {"old": 0, "lr": 0.0001, "depth": 1,
                  "contrast": 1., "distill": 0., "preview": 0}
        teacher = {"strategies": {"p": policy}}
        engine = SimpleNamespace(pick=lambda *_: ("p", policy))
        school = SimpleNamespace(stage="MAIN", grade="B", visits=0,
                                 champions={"A": {"optimizer_step": 1}})
        course = _visit_program()
        miss = {
            "id": "historic:wrong:xor", "source_id": "historic:wrong:xor",
            "capability": "B.XOR", "answer_kind": "binary",
            "gold": "FALSE", "tokens": [8, 9, 10],
        }
        receipt = {
            "teacher": teacher, "generation": 1, "run_id": "fresh-score",
            "school": {}, "teacher_misses": [miss],
            "teacher_miss_exposures": {miss["id"]: 0},
            "config": {}, "answer_ids": [6, 7],
            "curriculum_mode": "fixture-school",
        }
        optimizer = SimpleNamespace(
            learning_rate=0.0001,
            state={"step": SimpleNamespace(item=lambda: 1)})
        scored_ids = []

        def source_rows(*_args, **kwargs):
            return _rows(kwargs["capability"])

        def capture_score(_mx, _params, rows, *_args):
            scored_ids.extend(row["id"] for row in rows)
            raise _BatchCaptured("FRESH_SCORE_ROWS_CAPTURED")

        with (patch('bilqis_mlx.runtime.state._state_from_json', return_value=school),
              patch('bilqis_mlx.runtime.admission._read_executable_factory_release_artifact',
                    return_value=_visit_release(course)),
              patch('bilqis_mlx.factory.schedule.schedule_program_from_executable_release',
                    return_value=course),
              patch('bilqis_mlx.curriculum.scheduler.next_capability', return_value="B.XOR"),
              patch('bilqis_mlx.runtime.assessment._draw_live_rows', side_effect=source_rows),
              patch('bilqis_mlx.learning.lesson_guidance._frozen_confidence_champions',
                    return_value=()),
              patch('bilqis_mlx.learning.lesson_guidance._frozen_grade_soup_votes',
                    return_value=((), ())),
              patch('bilqis_mlx.learning.student_ops._train_score',
                    side_effect=capture_score)):
            with self.assertRaisesRegex(
                    _BatchCaptured, "FRESH_SCORE_ROWS_CAPTURED"):
                trainer._take_visit(
                    None, Path("/never-opened"), receipt, {}, course, engine,
                    {}, optimizer, {}, steps_per_visit=1, batch_size=8,
                    reserve_gib=0., source_root=Path("/not-used"),
                    learning_settings=Settings())

        self.assertNotIn(miss["id"], scored_ids)
        self.assertEqual(scored_ids, [row["id"] for row in _rows("B.XOR")])

    def test_visit_consumes_prefetched_source_packet_without_serial_step_redraw(self):
        engine, school, course, receipt, optimizer = _prefetch_visit_fixture()
        captured = []
        serial_draws = []
        submitted_requests = []

        def serial_source_rows(*_args, **kwargs):
            serial_draws.append(kwargs["seed"])
            if len(serial_draws) > 1:
                raise AssertionError("STEP_SOURCE_REDRAW_BYPASSED_PREFETCH")
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
              patch('bilqis_mlx.runtime.assessment._draw_live_rows', side_effect=serial_source_rows),
              patch('bilqis_mlx.curriculum.scheduler.assessment_capabilities', return_value=("B.XOR",)),
              patch('bilqis_mlx.learning.lesson_guidance._frozen_confidence_champions', return_value=()),
              patch('bilqis_mlx.learning.lesson_guidance._frozen_grade_soup_votes', return_value=((), ())),
              patch('bilqis_mlx.learning.student_ops._train_score', return_value=0.5),
              patch('bilqis_mlx.runtime.candidate_evidence._learning_probe_rows',
                           return_value=(_rows("B.XOR")[:6], set(), 0)),
              patch('bilqis_mlx.learning.student_ops._predictions', side_effect=wrong_predictions),
              patch('bilqis_mlx.learning.learning_experiment.fork_student', return_value=({}, optimizer)),
              patch('bilqis_mlx.diagnostics.teaching.inspect_lesson_step',
                           side_effect=ValueError("fixture methodology unavailable")),
              patch("bilqis_mlx.learning.fragile_replay.load_replay_rows", return_value=()),
              patch('bilqis_mlx.learning.student_ops._train_step', side_effect=inspect_batch)):
            with self.assertRaisesRegex(_BatchCaptured, "STOP_BEFORE_ANY_OPTIMIZER"):
                trainer._take_visit(
                    None, Path("/never-opened"), receipt, {}, course, engine, {},
                    optimizer, {}, steps_per_visit=1, batch_size=8, reserve_gib=0.,
                    source_root=Path("/not-used"), learning_settings=Settings(),
                    source_prefetch_executor=_InlinePrefetchExecutor(submitted_requests),
                    source_prefetch_workers=1)

        self.assertEqual(len(serial_draws), 1,
                         "Only the visit-level score draw should use the serial path")
        self.assertEqual(len(submitted_requests), 1)
        self.assertEqual(submitted_requests[0]["executable_release"].release_sha256,
                         "f" * 64)
        self.assertEqual(len(captured), 8)
        self.assertTrue(all(row["id"].startswith("prefetch:") for row in captured))

    def test_binary_grade_b_visit_rehearses_source_bound_grade_a_when_requested(self):
        delivered = self._visit_selection(old=16)
        self.assertIn("A.IDENTITY", delivered)
        self.assertIn("B.XOR", delivered)

    def test_ungraduated_debt_gets_requested_rehearsal_without_a_champion(self):
        delivered = self._visit_selection(old=16, carried_debt=True)
        self.assertIn("A.IDENTITY", delivered)
        self.assertIn("B.XOR", delivered)
        self.assertEqual(set(self._visit_selection(old=0, carried_debt=True)), {"B.XOR"})
