"""Disk gate preserves telemetry before the fail-closed write assertion."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import TestCase

from unittest.mock import patch
from bilqis_mlx.runtime.operator_session import operator_disk as subject


def operator_disk_ready(run_dir, reserve_gib, visits, disk, timing_trace):
    with patch.multiple(subject, disk=disk, timing_trace=timing_trace):
        return subject.operator_disk_ready(run_dir, reserve_gib, visits)


class DiskGateTest(TestCase):
    def test_insufficient_disk_skips_assertion(self):
        events = []
        @contextmanager
        def span(name, **kwargs):
            events.append(name)
            yield
        disk = SimpleNamespace(headroom_snapshot=lambda *a, **k: {"sufficient": False},
                               assert_headroom=lambda *a, **k: events.append("assert"))
        self.assertFalse(operator_disk_ready("run", 100, 2, disk, SimpleNamespace(trace_span=span)))
        self.assertEqual(events, ["DISK_HEADROOM"])

    def test_sufficient_disk_rechecks_before_visit(self):
        events = []
        @contextmanager
        def span(name, **kwargs):
            events.append((name, kwargs))
            yield
        disk = SimpleNamespace(headroom_snapshot=lambda *a, **k: {"sufficient": True},
                               assert_headroom=lambda *a, **k: events.append(("assert", k)))
        self.assertTrue(operator_disk_ready("run", 100, 2, disk, SimpleNamespace(trace_span=span)))
        self.assertEqual(events, [("DISK_HEADROOM", {"visit_index": 3}),
            ("DISK_HEADROOM_ASSERT", {"visit_index": 3}),
            ("assert", {"required_bytes": 600_000_000, "reserve_gib": 100})])
