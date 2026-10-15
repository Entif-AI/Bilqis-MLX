"""A human must know why a training invocation ended, without rerunning it."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.cli import parse_args, human_stop_summary, _inspect
from bilqis_mlx.disk import headroom_snapshot, assert_headroom
from bilqis_mlx.grade_a_dashboard import build
from bilqis_mlx.grade_a_trainer import session_stop_reason, _record


class HumanSessionStopTests(unittest.TestCase):
    def test_minutes_are_the_default_limit_not_hidden_48_visit_ceiling(self):
        args = parse_args(["train", "--minutes", "90", "--resume"])
        self.assertEqual(args.minutes, 90)
        self.assertEqual(args.max_visits, 0)
        self.assertEqual(parse_args(["train", "--max-visits", "4"]).max_visits, 4)

    def test_explicit_limit_and_time_limit_are_different_stop_reasons(self):
        ctx = dict(stage="MAIN", minutes=90, visits=48)
        self.assertEqual(session_stop_reason(**ctx, elapsed_seconds=150, max_visits=48),
                         "VISIT_LIMIT_REACHED")
        self.assertIsNone(session_stop_reason(**ctx, elapsed_seconds=150, max_visits=0))
        self.assertEqual(session_stop_reason(**ctx, elapsed_seconds=5400, max_visits=0),
                         "TIME_LIMIT_REACHED")
        self.assertEqual(session_stop_reason(**ctx, elapsed_seconds=5400, max_visits=48),
                         "TIME_LIMIT_REACHED")

    def test_pending_exam_finishes_before_normal_stop_and_mastery_wins(self):
        self.assertIsNone(session_stop_reason(stage="ASSESS_MAIN", elapsed_seconds=5401,
                                              minutes=90, visits=48, max_visits=48))
        self.assertEqual(session_stop_reason(stage="AWAITING_NEXT_GRADE",
                         elapsed_seconds=20, minutes=90, visits=2, max_visits=48),
                         "GRADE_A_AWAITING_NEXT_GRADE")

    def test_durable_stop_event_appears_in_snapshot_after_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            event = {"event": "GRADE_A_SESSION_STOPPED", "stop_reason": "VISIT_LIMIT_REACHED",
                     "visits_this_command": 48, "committed_total_visits": 144,
                     "optimizer_step": 119064, "generation": 181,
                     "max_visits": 48, "minutes": 90, "elapsed_seconds": 119.5}
            with redirect_stdout(io.StringIO()):
                _record(run, event)
            self.assertEqual(json.loads((run / "events.jsonl").read_text()), event)
            board = build(run, stream=io.StringIO())
            view = board.render(width=120, height=44)
            self.assertIn("VISIT_LIMIT_REACHED", view)
            self.assertIn("48", view)
            self.assertFalse((run / "state.json").exists())

    def test_operator_receipt_explains_stop_and_resume(self):
        result = {"stop_reason": "VISIT_LIMIT_REACHED", "visits_this_command": 48,
                  "elapsed_seconds": 131.2, "optimizer_step": 119064}
        summary = human_stop_summary(result)
        self.assertIn("explicitly configured --max-visits", summary)
        self.assertIn("48 visits", summary)
        self.assertIn("--human-run --resume", summary)
        result["stop_reason"] = "GRADE_A_AWAITING_NEXT_GRADE"
        self.assertNotIn("--human-run --resume", human_stop_summary(result))

    def test_disk_budget_breach_is_proven_without_writing_any_checkpoint(self):
        # 100.28 GiB free is insufficient for 100 GiB reserve + 600 MB.
        free = int(100.28 * 1024 ** 3)
        with tempfile.TemporaryDirectory() as directory, patch(
                "bilqis_mlx.disk.shutil.disk_usage",
                return_value=SimpleNamespace(total=1000 * 1024 ** 3,
                                             used=0, free=free)):
            report = headroom_snapshot(Path(directory),
                                       required_bytes=600_000_000, reserve_gib=100.)
            self.assertFalse(report["sufficient"])
            self.assertEqual(report["free_bytes"], free)
            self.assertEqual(report["reserve_bytes"], 100 * 1024 ** 3)
            with self.assertRaisesRegex(RuntimeError, "DISK_BUDGET_EXHAUSTED"):
                assert_headroom(Path(directory), required_bytes=600_000_000,
                                reserve_gib=100.)

    def test_disk_reserve_normal_stop_explains_why_training_did_not_continue(self):
        result = {"stop_reason": "DISK_RESERVE_REACHED",
                  "visits_this_command": 849, "elapsed_seconds": 389.2,
                  "optimizer_step": 132648, "disk_free_gib": 100.28,
                  "disk_reserve_gib": 100.0, "disk_next_visit_gib": .559}
        output = human_stop_summary(result)
        self.assertIn("DISK_RESERVE_REACHED", output)
        self.assertIn("100.28 GiB", output)
        self.assertIn("reserve", output.lower())
        self.assertIn("--human-run --resume", output)

    def test_status_uses_only_stop_matching_latest_model_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            state = {"schema": "bilqis.mlx.human-grade-a-trainer/v1",
                     "generation": 23, "result": "ACTIVE_GRADE_A",
                     "school": {"grade_index": 0, "active_grades": ["A"],
                                "stage": "MAIN", "visits": 20,
                                "current_student": {"sha256": "a" * 64,
                                                    "optimizer_step": 117080},
                                "champions": {}},
                     "teacher": {"events": 10, "strategies": {}}, "last_exam": None}
            (run / "state.json").write_text(json.dumps(state))
            event = {"event": "GRADE_A_SESSION_STOPPED",
                     "stop_reason": "TIME_LIMIT_REACHED", "generation": 23,
                     "optimizer_step": 117080, "visits_this_command": 20,
                     "elapsed_seconds": 5400.6, "minutes": 90, "max_visits": 0}
            with redirect_stdout(io.StringIO()):
                _record(run, event)
            self.assertEqual(_inspect(run)["last_session_stop"]["reason"],
                             "TIME_LIMIT_REACHED")
            state["generation"] += 1
            (run / "state.json").write_text(json.dumps(state))
            self.assertIsNone(_inspect(run)["last_session_stop"])


if __name__ == "__main__":
    unittest.main()
