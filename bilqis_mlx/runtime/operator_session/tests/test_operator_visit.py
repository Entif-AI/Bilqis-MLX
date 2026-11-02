"""Autonomy visit evidence must be present in the durable delivery outbox."""
from contextlib import nullcontext
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.runtime.operator_session import operator_visit as subject


class VisitTest(TestCase):
    def test_missing_durable_delivery_fails_after_flush(self):
        events = []
        receipt = {"generation": 1, "school": {}, "_pending_visit_events": [
            {"autonomy_teaching": {"specimen_content_sha256": "digest"}}]}
        school = SimpleNamespace(stage="MAIN", grade="A", current_student=SimpleNamespace(sha256="old", optimizer_step=1))
        work = SimpleNamespace(teaching_option_ids=("option",), failed_evidence=object())
        replacements = dict(
            _runtime_timing_trace=SimpleNamespace(trace_span=lambda *a, **k: nullcontext()),
            _runtime_checkpoints=SimpleNamespace(_notify_viewer=lambda event: events.append("notify")),
            _runtime_visits=SimpleNamespace(_take_visit=lambda *a, **k: receipt),
            _runtime_boundary_commit=SimpleNamespace(_flush_working_student=lambda *a, **k: events.append("flush") or receipt),
            _runtime_state=SimpleNamespace(_state_from_json=lambda *a: school),
            _runtime_release_adoption=SimpleNamespace(_schedule_for_receipt=lambda *a: None))
        with patch.multiple(subject, **replacements):
            with self.assertRaisesRegex(ValueError, "^AUTONOMY_TEACHING_DURABLE_EVENT_MISSING$"):
                subject.execute_operator_visit(mx=None, run_dir="run", receipt=receipt, manifest=None,
                    course=None, engine=None, params=None, optimizer=None, graph=None,
                    steps_per_visit=1, batch_size=2, reserve_gib=1, source_root="source",
                    learning_settings=None, boolean_association_bridge=False, autonomy_teaching_work=work,
                    source_prefetch_executor=None, source_prefetch_workers=0, visits=0, school=school,
                    autonomous_curriculum=True, experiment_budget=None, autonomy_session=None)
        self.assertEqual(events, ["notify", "flush"])
