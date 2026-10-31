"""Low-overhead timing markers are durable before the traced run exits."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from bilqis_mlx.runtime.timing_trace import TimingTrace, trace_mark, trace_span


class TimingTraceTests(unittest.TestCase):
    def test_markers_are_written_before_context_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.jsonl"
            with TimingTrace(path, metadata={"max_visits": 12}):
                trace_mark("VISIT_START", capability="B.XOR")
                self.assertTrue(path.is_file())
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                self.assertEqual([row["record"] for row in rows], ["HEADER", "MARK"])
                self.assertEqual(rows[1]["name"], "VISIT_START")
                self.assertEqual(rows[1]["capability"], "B.XOR")
            rows = [json.loads(line) for line in path.read_text().splitlines()]

        self.assertEqual(rows[-1]["record"], "FOOTER")
        self.assertEqual(rows[0]["metadata"]["max_visits"], 12)

    def test_span_writes_start_and_end_with_duration(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.jsonl"
            with TimingTrace(path):
                with trace_span("RETENTION_SCORE", step=3):
                    pass
            rows = [json.loads(line) for line in path.read_text().splitlines()]

        span = [row for row in rows if row["record"].startswith("SPAN_")]
        self.assertEqual([row["record"] for row in span], ["SPAN_START", "SPAN_END"])
        self.assertEqual(span[0]["name"], "RETENTION_SCORE")
        self.assertEqual(span[1]["step"], 3)
        self.assertGreaterEqual(span[1]["duration_ns"], 0)
        self.assertGreaterEqual(span[1]["duration_ms"], 0)
        self.assertTrue(all(row["delta_ns"] >= 0 for row in span))

    def test_marker_survives_process_exit_without_context_unwind(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.jsonl"
            repo = Path(__file__).resolve().parents[4]
            script = (
                "import os,sys\n"
                f"sys.path.insert(0,{str(repo)!r})\n"
                "from pathlib import Path\n"
                "from bilqis_mlx.runtime.timing_trace import TimingTrace,trace_mark\n"
                f"trace=TimingTrace(Path({str(path)!r}))\n"
                "trace.__enter__()\n"
                "trace_mark('BEFORE_HARD_EXIT',value=42)\n"
                "os._exit(0)\n"
            )
            completed = subprocess.run([sys.executable, "-c", script], check=False)
            self.assertEqual(completed.returncode, 0)
            rows = [json.loads(line) for line in path.read_text().splitlines()]

        self.assertEqual([row["record"] for row in rows], ["HEADER", "MARK"])
        self.assertEqual(rows[1]["name"], "BEFORE_HARD_EXIT")
        self.assertEqual(rows[1]["value"], 42)
