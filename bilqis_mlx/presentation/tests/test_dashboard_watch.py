"""A detached observer must keep receiving a separate trainer's durable events."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from bilqis_mlx.presentation.dashboard import build
from bilqis_mlx.presentation.dashboard_watch import JournalReplaced, JournalTail, watch
from bilqis_mlx.presentation.run_discovery import (
    AmbiguousActiveRun, operator_lock_held, select_run,
)


class DashboardWatchTests(unittest.TestCase):
    def test_automatically_selects_the_only_active_cross_worktree_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots = (Path(tmp) / "canonical", Path(tmp) / "codex")
            first = roots[0] / "runs" / "school-mlx-v1"
            second = roots[1] / "runs" / "issue-349-experiments" / "primary"
            for candidate in (first, second):
                candidate.mkdir(parents=True)
                (candidate / "state.json").write_text("{}")
            chosen, live = select_run(
                first, worktrees=roots,
                lock_probe=lambda path: path.parent == second.resolve(),
            )
            self.assertEqual(chosen, second.resolve())
            self.assertTrue(live)

    def test_refuses_to_guess_between_two_active_students(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b = root / "runs" / "alpha", root / "runs" / "beta"
            for candidate in (a, b):
                candidate.mkdir(parents=True)
                (candidate / "state.json").write_text("{}")
            with self.assertRaisesRegex(AmbiguousActiveRun, "--run-dir"):
                select_run(a, worktrees=(root,), lock_probe=lambda _: True)

    def test_stale_lock_file_is_not_an_active_trainer(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / ".grade-a-operator.lock"
            lock.touch()
            self.assertFalse(operator_lock_held(lock))

    def test_exclusive_operator_lock_is_detected_without_interrupting_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / ".grade-a-operator.lock"
            child = (
                "import fcntl,sys; "
                "f=open(sys.argv[1],'a+'); "
                "fcntl.flock(f.fileno(),fcntl.LOCK_EX); "
                "print('LOCKED',flush=True); sys.stdin.readline()"
            )
            with subprocess.Popen(
                [sys.executable, "-c", child, str(lock)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            ) as owner:
                self.assertEqual(owner.stdout.readline().strip(), "LOCKED")
                self.assertTrue(operator_lock_held(lock))
                owner.communicate("\n", timeout=5)
                self.assertEqual(owner.returncode, 0)
            self.assertFalse(operator_lock_held(lock))

    def test_snapshot_tail_handoff_consumes_each_new_complete_event_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text(json.dumps({"event": "SCHOOL_SESSION_STARTED",
                                        "generation": 1, "optimizer_step": 4}) + "\n")
            board = build(Path(tmp), stream=io.StringIO())
            tail = JournalTail(path, board.journal_offset, board.journal_identity)
            self.assertEqual(tail.poll(), ())
            with path.open("ab") as output:
                output.write(b'{"event":"SCHOOL_EXAM_COMMITTED","generation":2')
            self.assertEqual(tail.poll(), ())
            with path.open("ab") as output:
                output.write(b'}\n')
            self.assertEqual(tail.poll(), ({"event": "SCHOOL_EXAM_COMMITTED",
                                            "generation": 2},))
            self.assertEqual(tail.poll(), ())

    def test_replacement_is_detected_instead_of_silently_missing_new_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text('{"event":"ONE"}\n')
            board = build(Path(tmp), stream=io.StringIO())
            tail = JournalTail(path, board.journal_offset, board.journal_identity)
            os.replace(path, Path(tmp) / "events.old")
            path.write_text('{"event":"TWO"}\n')
            with self.assertRaises(JournalReplaced):
                tail.poll()

    def test_watcher_redraws_when_another_process_appends_without_writing_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "events.jsonl"
            path.write_text('{"event":"SCHOOL_SESSION_STARTED","grade":"A","optimizer_step":3}\n')
            original = path.read_bytes()
            stream = io.StringIO()
            wait_calls = []

            def append_once(seconds):
                wait_calls.append(seconds)
                if len(wait_calls) == 1:
                    with path.open("ab") as output:
                        output.write(b'{"event":"SCHOOL_SESSION_STOPPED","stop_reason":"TIME_LIMIT_REACHED","grade":"A","optimizer_step":3,"visits_this_command":1,"elapsed_seconds":8.0}\n')

            board = watch(root, stream=stream, wait=append_once, max_polls=2)
            self.assertIn("FOLLOW", stream.getvalue())
            self.assertIn("TIME_LIMIT_REACHED", stream.getvalue())
            self.assertTrue(board.mode.startswith("STOPPED"))
            self.assertEqual(path.read_bytes(), original +
                             b'{"event":"SCHOOL_SESSION_STOPPED","stop_reason":"TIME_LIMIT_REACHED","grade":"A","optimizer_step":3,"visits_this_command":1,"elapsed_seconds":8.0}\n')
            self.assertFalse((root / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
