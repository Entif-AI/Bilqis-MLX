"""Retention integration contracts; original evidence and boundaries preserved."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from bilqis_mlx import trainer as trainer
from bilqis_mlx.learning.learning_experiment import Settings, earlier_grade_capabilities
from bilqis_mlx.factory.schedule import ScheduleCapability, ScheduleGrade, ScheduleProgram
from tests.integration.retention.fixtures import VisitFixture, _BatchCaptured, _rows, _visit_program, _visit_release


class CustodyTests(VisitFixture, unittest.TestCase):
    def test_one_unresolved_semantic_is_present_in_every_optimizer_batch(self):
        policy = {"old": 0, "lr": 0.0001, "depth": 1,
                  "contrast": 1., "distill": 0., "preview": 0}
        teacher = {"strategies": {"p": policy}}
        engine = SimpleNamespace(pick=lambda *_: ("p", policy))
        school = SimpleNamespace(stage="MAIN", grade="B", visits=0,
                                 champions={"A": {"optimizer_step": 1}})
        course = _visit_program()
        target = {
            "id": "weak:xor:true", "source_id": "weak:xor:true",
            "capability": "B.XOR", "answer_kind": "binary",
            "gold": "TRUE", "tokens": [8, 9, 10],
        }
        receipt = {
            "teacher": teacher, "generation": 1, "run_id": "weakness-target",
            "school": {}, "teacher_misses": [target],
            "teacher_miss_exposures": {target["id"]: 0},
            "config": {}, "answer_ids": [6, 7],
            "curriculum_mode": "fixture-school",
        }
        optimizer = SimpleNamespace(
            learning_rate=0.0001,
            state={"step": SimpleNamespace(item=lambda: 1)})
        batches = []

        def source_rows(*_args, **kwargs):
            return _rows(kwargs["capability"])

        def capture_three_batches(_mx, _parameters, _optimizer, rows,
                                  *_args, **_kwargs):
            batches.append(tuple(row["id"] for row in rows))
            if len(batches) == 3:
                raise _BatchCaptured("THREE_TARGETED_BATCHES_CAPTURED")
            return 0.1, 0.1

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
                    return_value=()),
              patch('bilqis_mlx.learning.student_ops._train_step',
                           side_effect=capture_three_batches)):
            with self.assertRaisesRegex(
                    _BatchCaptured, "THREE_TARGETED_BATCHES_CAPTURED"):
                trainer._take_visit(
                    None, Path("/never-opened"), receipt, {}, course, engine, {},
                    optimizer, {}, steps_per_visit=3, batch_size=8,
                    reserve_gib=0., source_root=Path("/not-used"),
                    learning_settings=Settings())

        self.assertEqual(len(batches), 3)
        self.assertTrue(all(target["id"] in batch for batch in batches))

    def test_older_grade_pool_excludes_target_grade_and_future_grades(self):
        program = ScheduleProgram(
            program_digest="a" * 64,
            grades=tuple(ScheduleGrade(
                grade,
                (ScheduleCapability(cap, 12),),
                ((cap,),),
                "b" * 64,
            ) for grade, cap in (
                ("A", "A.IDENTITY"), ("B", "B.XOR"),
                ("C", "C.COUNT"), ("D", "D.NEW"))),
            program_complete=False,
        )
        completed = {"A": object(), "B": object(), "C": object(),
                     "D": object()}
        self.assertEqual(earlier_grade_capabilities(program, completed, "B.XOR"),
                         ("A.IDENTITY",))
        self.assertEqual(earlier_grade_capabilities(program, completed, "C.COUNT"),
                         ("A.IDENTITY", "B.XOR"))
        self.assertEqual(earlier_grade_capabilities(program, completed, "A.IDENTITY"),
                         ())
        with self.assertRaisesRegex(ValueError, "UNKNOWN_TARGET_GRADE"):
            earlier_grade_capabilities(program, completed, "E.UNKNOWN")

    def test_fresh_fragile_preservation_covers_truth_tables_without_exam_ids(self):
        fixed = []
        fresh_by_cap = {}
        def operand(kind):
            if kind == "EQ":
                return {"kind": "compare", "operator": "EQ", "args": [
                    {"kind": "entity", "name": "A"},
                    {"kind": "entity", "name": "B"}]}
            return {"kind": "relation", "name": kind, "args": [
                {"kind": "entity", "name": "A"},
                {"kind": "entity", "name": "B"}]}
        for capability in ("B.OR", "B.XOR"):
            candidates = []
            for index, bits in enumerate((
                    (False, False), (False, True), (True, False), (True, True))):
                gold = ("TRUE" if (any(bits) if capability == "B.OR"
                                   else bits[0] != bits[1]) else "FALSE")
                kinds = (("PARENT", "EQ") if index % 2 == 0
                         else ("LINK", "PARENT"))
                shape = {
                    "universe_size": 3 + index % 2,
                    "record": {"query": {
                        "kind": "apply", "operator": capability[2:],
                        "args": [operand(kind) for kind in kinds]}},
                }
                fixed.append({"id": f"exam:{capability}:{index}",
                              "capability": capability, "gold": gold,
                              "operand_truths": list(bits), "tokens": [1, 2, 3],
                              **shape})
                candidates.append({"id": f"fresh:{capability}:{index}",
                                   "capability": capability, "gold": gold,
                                   "operand_truths": list(bits), "tokens": [4, 5, 6],
                                   **shape})
            fresh_by_cap[capability] = candidates

        def draw(*_args, **kwargs):
            return fresh_by_cap[kwargs["capability"]]

        school = SimpleNamespace()
        receipt = {"run_id": "preservation", "generation": 4}
        program = _visit_program()
        with (patch("bilqis_mlx.learning.fragile_replay.load_replay_rows",
                    return_value=tuple(fixed)),
              patch('bilqis_mlx.curriculum.scheduler.assessment_capabilities',
                           return_value=("B.AND", "B.OR", "B.XOR")),
              patch('bilqis_mlx.runtime.assessment._draw_live_rows', side_effect=draw)):
            selected = trainer._fresh_fragile_preservation_rows(
                Path("/unused"), Path("/source"), {}, receipt, program, school,
                "B.AND", step=1, batch_size=32)
        self.assertEqual(len(selected), 8)
        self.assertFalse({row["id"] for row in selected} &
                         {row["id"] for row in fixed})
        self.assertEqual(
            {(row["capability"], tuple(row["operand_truths"])) for row in selected},
            {(capability, bits)
             for capability in ("B.OR", "B.XOR")
             for bits in ((False, False), (False, True), (True, False), (True, True))},
        )
