"""Finish flushes before publishing the stop receipt."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from unittest.mock import patch as patch_modules
from bilqis_mlx.runtime.operator_session import operator_finish as subject


def finish_operator_session(**kwargs):
    names = ['_runtime_timing_trace', '_runtime_boundary_commit', '_runtime_state', '_runtime_release_adoption', '_runtime_disk', '_learning_stagnation_control', '_runtime_checkpoints', '_runtime_session', '_time']
    replacements = {name: kwargs.pop(name) for name in names}
    with patch_modules.multiple(subject, **replacements):
        return subject.finish_operator_session(**kwargs)



class FinishTest(TestCase):
    def test_normal_finish_flushes_then_records_stop(self):
        events = []
        receipt = {"result": "OK", "school": {}, "generation": 2, "run_id": "r", "last_exam": None}
        student = SimpleNamespace(optimizer_step=4, sha256="student")
        school = SimpleNamespace(current_student=student, visits=3, stage="MAIN", grade="A")
        @contextmanager
        def span(name, **kwargs):
            events.append(name)
            yield
        trace = SimpleNamespace(trace_span=span, trace_mark=lambda *a, **k: events.append(a[0]))
        boundary = SimpleNamespace(_flush_working_student=lambda *a, **k: events.append("flush") or receipt)
        checkpoints = SimpleNamespace(_record=lambda _, event: events.append(event["event"]))
        state = SimpleNamespace(_state_from_json=lambda *a: school)
        adoption = SimpleNamespace(_schedule_for_receipt=lambda *a: None)
        disk = SimpleNamespace(headroom_snapshot=lambda *a, **k: dict(free_bytes=4, reserve_bytes=2, estimated_write_bytes=1))
        stagnation = SimpleNamespace(end_of_run_alerts=lambda x: (), quarantined_capabilities=lambda x: ())
        session = SimpleNamespace(_resume_command=lambda *a, **k: "resume")
        with patch("bilqis_mlx.state_archive.compact_states", return_value={"compressed_generations": 0}):
            result = finish_operator_session(mx=None, run_dir="r", receipt=receipt,
                manifest=None, course=None, params=None, optimizer=None, graph=None,
                reserve_gib=1, source_root="s", experiment_budget=None, flash_mode=False,
                visits=1, start=0, reason="LIMIT", minutes=90, max_visits=1,
                source_prefetch_workers=0, source_prefetch_executor=None,
                boolean_association_bridge=False, autonomous_curriculum=False,
                learning_settings=None, _runtime_timing_trace=trace,
                _runtime_boundary_commit=boundary, _runtime_state=state,
                _runtime_release_adoption=adoption, _runtime_disk=disk,
                _learning_stagnation_control=stagnation, _runtime_checkpoints=checkpoints,
                _runtime_session=session, _time=SimpleNamespace(monotonic=lambda: 2))
        self.assertEqual(result["stop_reason"], "LIMIT")
        self.assertEqual(result["optimizer_step"], 4)
        self.assertLess(events.index("flush"), events.index("SCHOOL_SESSION_STOPPED"))
        self.assertLess(events.index("SCHOOL_SESSION_STOPPED"), events.index("STATE_ARCHIVE_COMPACT"))

    def test_budget_failure_prevents_flush_and_stop_receipt(self):
        events = []
        @contextmanager
        def span(name, **kwargs):
            events.append(name)
            yield
        budget = SimpleNamespace(assert_can_allocate=lambda _: (_ for _ in ()).throw(ValueError("BUDGET")))
        with self.assertRaisesRegex(ValueError, "^BUDGET$"):
            finish_operator_session(mx=None, run_dir="r", receipt={}, manifest=None, course=None,
                params=None, optimizer=None, graph=None, reserve_gib=1, source_root="s",
                experiment_budget=budget, flash_mode=False, visits=0, start=0, reason="LIMIT",
                minutes=1, max_visits=1, source_prefetch_workers=0, source_prefetch_executor=None,
                boolean_association_bridge=False, autonomous_curriculum=False, learning_settings=None,
                _runtime_timing_trace=SimpleNamespace(trace_span=span), _runtime_boundary_commit=None,
                _runtime_state=None, _runtime_release_adoption=None, _runtime_disk=None,
                _learning_stagnation_control=None, _runtime_checkpoints=None, _runtime_session=None,
                _time=None)
        self.assertEqual(events, ["FLUSH_WORKING_STUDENT"])

    def test_archive_failure_records_block_after_stop(self):
        events = []
        @contextmanager
        def span(name, **kwargs):
            events.append(name)
            yield
        with patch.multiple(subject,
                            _runtime_timing_trace=SimpleNamespace(trace_span=span),
                            _runtime_checkpoints=SimpleNamespace(_record=lambda _, event: events.append(event))):
            with patch("bilqis_mlx.state_archive.compact_states", side_effect=OSError("full")):
                result = subject._compact_stop_states("run", {"generation": 9})
        self.assertEqual(result, {"error": "full", "compressed_generations": 0})
        self.assertEqual(events[0], "STATE_ARCHIVE_COMPACT")
        self.assertEqual(events[1], {"event": "SCHOOL_STATE_ARCHIVE_BLOCKED", "generation": 9, "reason": "full"})

    def test_stop_event_retains_disk_and_resume_details(self):
        events = []
        receipt = {"generation": 2, "run_id": "run", "stagnation_session": {"session_id": "s"}}
        school = SimpleNamespace(current_student=SimpleNamespace(optimizer_step=4, sha256="sha"),
                                 visits=3, stage="AWAITING_NEXT_GRADE", grade="A")
        disk = {"free_bytes": 4, "reserve_bytes": 2, "estimated_write_bytes": 1}
        with patch.object(subject, "_runtime_checkpoints", SimpleNamespace(_record=lambda _, event: events.append(event))):
            subject._record_session_stopped("run", receipt, school, disk, "LIMIT", 1, 90, 2,
                1.5, 2, None, False, False, False, (), ())
        self.assertEqual(events[0]["event"], "SCHOOL_SESSION_STOPPED")
        self.assertFalse(events[0]["resume_required"])
        self.assertEqual(events[0]["source_prefetch_workers"], 0)
        self.assertEqual(events[0]["estimated_write_bytes"], 1)
