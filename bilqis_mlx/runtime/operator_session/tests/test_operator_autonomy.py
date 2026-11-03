"""Autonomy control stops before a visit when source coverage is blocked."""
from types import SimpleNamespace
from unittest import TestCase

from bilqis_mlx.factory.autonomy import AutonomyActionKind
from unittest.mock import patch
from bilqis_mlx.runtime.operator_session import operator_autonomy as subject
from bilqis_mlx.runtime.operator_session.operator_autonomy import DispatchControl


def dispatch_autonomy(**kwargs):
    names = ("_runtime_admission", "_runtime_checkpoints", "_runtime_state",
             "_learning_student_ops", "_dataclasses", "_runtime_exam_execution",
             "_curriculum_scheduler", "_bilqis_mlx_operator_vocabulary")
    replacements = {name: kwargs.pop(name) for name in names}
    with patch.multiple(subject, **replacements):
        return subject.dispatch_autonomy(**kwargs)


class AutonomyDispatchTest(TestCase):
    def test_source_coverage_stops_without_visit(self):
        events = []
        school = SimpleNamespace(grade="A", current_student=object())
        action = SimpleNamespace(kind=AutonomyActionKind.SOURCE_COVERAGE,
            deferred_obligation_ids=(), source_coverage_debt="missing")
        session = SimpleNamespace(refresh_release=lambda value: events.append("refresh"),
                                  action=lambda student: action)
        admission = SimpleNamespace(_read_executable_factory_release_artifact=lambda *a: "release")
        checkpoints = SimpleNamespace(_record=lambda _, event: events.append(event))
        result = dispatch_autonomy(autonomy_session=session, school=school, graph=None,
            receipt={"generation": 1}, run_dir="run", mx=None, params=None, optimizer=None,
            course=None, visits=2, autonomy_teaching_work=None, _runtime_admission=admission,
            _runtime_checkpoints=checkpoints, _runtime_state=None, _learning_student_ops=None,
            _dataclasses=None, _runtime_exam_execution=None, _curriculum_scheduler=None,
            _bilqis_mlx_operator_vocabulary=None)
        self.assertEqual(result[:2], (DispatchControl.STOP, "AUTONOMY_SOURCE_COVERAGE_REQUIRED"))
        self.assertEqual(result[4], 2)
        self.assertEqual(events[1]["event"], "SCHOOL_AUTONOMY_SOURCE_COVERAGE_BLOCKED")
        self.assertTrue(events[1]["model_and_optimizer_unchanged"])

    def invoke(self, action, session, school, scheduler, checkpoints):
        return dispatch_autonomy(autonomy_session=session, school=school, graph=None,
            receipt={"generation": 1}, run_dir="run", mx=None, params=None, optimizer=None,
            course="course", visits=2, autonomy_teaching_work=None,
            _runtime_admission=SimpleNamespace(_read_executable_factory_release_artifact=lambda *a: "release"),
            _runtime_checkpoints=checkpoints, _runtime_state=None, _learning_student_ops=None,
            _dataclasses=None, _runtime_exam_execution=SimpleNamespace(_school_result_label=lambda x: "OK"),
            _curriculum_scheduler=scheduler, _bilqis_mlx_operator_vocabulary=None)

    def test_qualification_continues_after_recording_visit(self):
        student = SimpleNamespace(optimizer_step=4, sha256="sha")
        school = SimpleNamespace(grade="A", current_student=student)
        action = SimpleNamespace(kind=AutonomyActionKind.QUALIFICATION, deferred_obligation_ids=())
        session = SimpleNamespace(refresh_release=lambda _: None, action=lambda _: action,
                                  evidence_complete=lambda _: ("A.X",))
        scheduler = SimpleNamespace(next_capability=lambda _: "A.X", visit=lambda *a: school)
        events = []
        checkpoints = SimpleNamespace(_advance=lambda *a, **k: {"generation": 2},
                                       _record=lambda _, event: events.append(event))
        result = self.invoke(action, session, school, scheduler, checkpoints)
        self.assertEqual(result[0], DispatchControl.CONTINUE)
        self.assertEqual(result[4], 3)
        self.assertEqual(events[0]["event"], "SCHOOL_AUTONOMY_QUALIFIED_VISIT_COMPLETED")
        self.assertEqual(events[0]["retained_optimizer_updates"], 0)

    def test_matching_teaching_proceeds_with_selected_work(self):
        work = SimpleNamespace(capability_id="A.X")
        school = SimpleNamespace(grade="A", current_student=object())
        action = SimpleNamespace(kind=AutonomyActionKind.TEACHING, deferred_obligation_ids=(), teaching_work=work)
        session = SimpleNamespace(refresh_release=lambda _: None, action=lambda _: action)
        with patch("bilqis_mlx.runtime.autonomy_live.scheduled_teaching_matches", return_value=True):
            result = self.invoke(action, session, school, None, None)
        self.assertEqual(result[0], DispatchControl.PROCEED)
        self.assertIs(result[5], work)
