"""Retention integration contracts; original evidence and boundaries preserved."""
from pathlib import Path
import json
import tempfile
import unittest
from bilqis_mlx.runtime.timing_trace import TimingTrace
from tests.integration.retention.fixtures import VisitFixture


class DeliveryTests(VisitFixture, unittest.TestCase):
    def test_real_visit_path_emits_coarse_write_ahead_timing_markers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.jsonl"
            with TimingTrace(path):
                self._visit_selection(old=0)
            rows = [json.loads(line) for line in path.read_text().splitlines()]

        names = [row.get("name") for row in rows]
        self.assertIn("VISIT_START", names)
        self.assertIn("VISIT_SOURCE_DRAW", names)
        self.assertIn("STEP_SOURCE_DRAW", names)
        self.assertIn("STEP_TRAIN", names)
