"""Session budget stops dispatch before any assessment or visit."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.runtime.operator_session import operator_iteration as subject
from bilqis_mlx.runtime.operator_session.operator_autonomy import DispatchControl


class IterationTest(TestCase):
    def test_time_limit_stops_before_assessment(self):
        receipt = {"school": {}}
        school = SimpleNamespace(stage="MAIN", grade="A")
        calls = []
        adoption = SimpleNamespace(
            _advance_numeric_profile=lambda *a, **k: (receipt, "course", "release", "schedule"),
            _auto_adopt_known_grade_boundary=lambda *a, **k: ("params", "optimizer", "graph", receipt, "course", False),
            _schedule_for_receipt=lambda *a: "schedule")
        session = SimpleNamespace(session_stop_reason=lambda **kw: calls.append(kw) or (None if len(calls) == 1 else "TIME_LIMIT"))
        replacements = dict(_runtime_release_adoption=adoption, _runtime_state=SimpleNamespace(_state_from_json=lambda *a: school),
            _runtime_reconciliation=SimpleNamespace(_reconcile_stagnation_scope=lambda *a: receipt),
            _runtime_session=session, _time=SimpleNamespace(monotonic=lambda: 5))
        with patch.multiple(subject, **replacements):
            result = subject.prepare_operator_iteration(experiment_budget=None, run_dir="run", receipt=receipt,
                course_a="a", source_root="source", graph="graph", course="course",
                executable_release="release", schedule_program="schedule", numeric_staircase=False,
                mx=None, manifest=None, params="params", optimizer="optimizer", reserve_gib=1,
                full_grade_b=True, autonomy_session=None, start=0, minutes=1, visits=0,
                max_visits=0, flash_mode=False, source_checkpoint="checkpoint",
                _stage_atlas_frontier_attempt=lambda *a: self.fail("staged frontier"))
        self.assertEqual(result[:2], (DispatchControl.STOP, "TIME_LIMIT"))
        self.assertEqual([call["stage"] for call in calls], ["MAIN", "MAIN"])
