"""High-resolution timing trace remains neural-inert and chronologically ordered."""
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.timing_trace import TimingTrace


def _inner_probe():
    return len((1, 2, 3, 4, 5, 6, 7))


def _outer_probe():
    return _inner_probe() + 1


class TimingTraceTests(unittest.TestCase):
    def test_function_boundaries_are_monotonic_and_include_durations(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.jsonl"
            package_root = Path(__file__).resolve().parents[1]
            with TimingTrace(path, package_root=package_root, include_c_calls=True,
                             metadata={"max_visits": 12}):
                self.assertEqual(_outer_probe(), 8)
            rows = [json.loads(line) for line in path.read_text().splitlines()]

        self.assertEqual(rows[0]["record"], "HEADER")
        self.assertTrue(rows[0]["include_c_calls"])
        self.assertEqual(rows[0]["metadata"]["max_visits"], 12)
        self.assertEqual(rows[-1]["record"], "FOOTER")
        events = [row for row in rows if row["record"] == "EVENT"]
        self.assertTrue(any(row["function"] == "_inner_probe" and
                            row["event"] == "call" for row in events))
        self.assertTrue(any(row["function"] == "c:len" and
                            row["event"] == "c_call" for row in events))
        returns = [row for row in events if row["function"] == "_inner_probe" and
                   row["event"] == "return"]
        self.assertEqual(len(returns), 1)
        self.assertGreaterEqual(returns[0]["duration_ns"], 0)
        self.assertEqual([row["sequence"] for row in events], list(range(len(events))))
        self.assertTrue(all(row["delta_ns"] >= 0 for row in events))

