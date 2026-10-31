"""Retention integration contracts; original evidence and boundaries preserved."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from bilqis_mlx import trainer as trainer
from bilqis_mlx.learning.learning_experiment import Settings
from bilqis_mlx.factory.schedule import ScheduleCapability, ScheduleGrade, ScheduleProgram


class _BatchCaptured(Exception):
    pass


def _rows(capability):
    return [{"id": f"{capability}:{index}", "source_id": f"{capability}:{index}",
             "capability": capability, "answer_kind": "binary",
             "gold": "TRUE" if index % 2 else "FALSE",
             "tokens": [3, 4, index + 5]}
            for index in range(12)]


def _visit_program():
    return ScheduleProgram(
        program_digest="c" * 64,
        grades=(
            ScheduleGrade(
                "A", (ScheduleCapability("A.IDENTITY", 12),),
                (("A.IDENTITY",),), "a" * 64),
            ScheduleGrade(
                "B", (ScheduleCapability("B.XOR", 12),),
                (("B.XOR",),), "b" * 64),
        ),
        program_complete=False,
    )


def _visit_release(program):
    # The prefetch identity is bound to the admitted executable release, not
    # merely to the scheduler's projected capability set.
    return SimpleNamespace(release_sha256="f" * 64,
                           execution_plan=SimpleNamespace(
        capabilities=tuple(program.capability_map.values())))


def _prefetch_visit_fixture():
    policy = {"old": 0, "lr": 0.0001, "depth": 1,
              "contrast": 1., "distill": 0., "preview": 0}
    teacher = {"strategies": {"p": policy}}
    engine = SimpleNamespace(pick=lambda *_: ("p", policy))
    school = SimpleNamespace(
        stage="MAIN", grade="B", visits=0,
        champions={"A": {"optimizer_step": 1}},
        current_student=SimpleNamespace(sha256="e" * 64))
    receipt = {
        "teacher": teacher, "generation": 7, "run_id": "prefetch-fixture",
        "school": {}, "teacher_misses": [], "config": {},
        "answer_ids": [6, 7], "curriculum_mode": "fixture-school",
        "semantic_graph_sha256": "d" * 64,
    }
    optimizer = SimpleNamespace(
        learning_rate=0.0001,
        state={"step": SimpleNamespace(item=lambda: 1)})
    return engine, school, _visit_program(), receipt, optimizer


class _ReadyResult:
    def __init__(self, value):
        self.value = value

    def result(self):
        return self.value


class _InlinePrefetchExecutor:
    def __init__(self, submitted_requests):
        self.submitted_requests = submitted_requests

    def submit(self, _fn, request):
        self.submitted_requests.append(request)
        fresh = [
            {"id": f"prefetch:{index}", "source_id": f"prefetch:{index}",
             "capability": "B.XOR", "answer_kind": "binary",
             "gold": "TRUE" if index % 2 else "FALSE", "tokens": [3, 4, index + 5]}
            for index in range(12)
        ]
        return _ReadyResult({
            "schema": "bilqis.mlx.source-prefetch/v1",
            "identity": request["identity"],
            "fresh": fresh,
            "prior": [],
            "preservation": [],
            "retention_support": [],
            "teaching_enrichment_rows": [],
        })


def _pointer(seed):
    return {"filename": "bundles/" + seed, "sha256": seed * 64,
            "optimizer_step": 100, "model_and_native_adamw": True}


def _exam(checkpoint, scores, *, cohort="c" * 64):
    return {"checkpoint_sha256": checkpoint["sha256"],
            "cohort_sha256": cohort, "rubric_sha256": "b" * 64,
            "assessment_scope_sha256": "e" * 64,
            "source_graph_sha256": "d" * 64,
            "scores": {cap: {"correct": correct, "total": 12}
                       for cap, correct in scores.items()}}


class VisitFixture:
    def _visit_selection(self, old, *, carried_debt=False):
        policy = {"old": old, "lr": 0.0001, "depth": 1,
                  "contrast": 1., "distill": 0., "preview": 0}
        teacher = {"strategies": {"p": policy}}
        engine = SimpleNamespace(pick=lambda *_: ("p", policy))
        school = SimpleNamespace(stage="MAIN", grade="B", visits=0,
                                 champions={} if carried_debt else {"A": {"optimizer_step": 1}},
                                 carried_mastery_debt=("A.IDENTITY",) if carried_debt else ())
        course = _visit_program()
        receipt = {"teacher": teacher, "generation": 1, "run_id": "disposable",
                   "school": {}, "teacher_misses": [], "config": {},
                   "answer_ids": [6, 7], "curriculum_mode": "fixture-school"}
        optimizer = SimpleNamespace(learning_rate=0.0001,
                                    state={"step": SimpleNamespace(item=lambda: 1)})
        captured = []

        def source_rows(*_args, **kwargs):
            return _rows(kwargs["capability"])

        def inspect_batch(_mx, _parameters, _optimizer, rows, *_args, **_kwargs):
            captured.extend(row["capability"] for row in rows)
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
              patch('bilqis_mlx.learning.learning_experiment.fork_student',
                           return_value=({}, optimizer)),
              patch('bilqis_mlx.diagnostics.teaching.inspect_lesson_step',
                           side_effect=ValueError("fixture methodology unavailable")),
              patch("bilqis_mlx.learning.fragile_replay.load_replay_rows", return_value=()),
              patch('bilqis_mlx.learning.student_ops._train_step', side_effect=inspect_batch)):
            with self.assertRaisesRegex(_BatchCaptured, "STOP_BEFORE_ANY_OPTIMIZER"):
                trainer._take_visit(None, Path("/never-opened"), receipt, {},
                                    course, engine, {}, optimizer, {},
                                    steps_per_visit=1, batch_size=8,
                                    reserve_gib=0., source_root=Path("/not-used"),
                                    learning_settings=Settings())
        self.assertEqual(len(captured), 8)
        return captured
