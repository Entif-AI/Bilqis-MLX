from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.bamf_writer_handoff import HandoffError, emit, verify


class WriterHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "work"
        self.remote = Path(self.temp.name) / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(self.remote)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "work", str(self.repo)], check=True)
        self.run_git("config", "user.email", "test@example.invalid")
        self.run_git("config", "user.name", "Test")
        (self.repo / "file.txt").write_text("initial\n")
        self.run_git("add", ".")
        self.run_git("commit", "-qm", "initial")
        self.run_git("remote", "add", "origin", str(self.remote))
        self.run_git("push", "-q", "-u", "origin", "work")

    def run_git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def test_same_worktree_same_branch_head_and_dirty_state_resumes(self) -> None:
        (self.repo / "local.txt").write_text("keep this\n")
        payload = emit(self.repo, 709, "epoch-709")
        self.assertEqual("CONTINUATION_MATCH", verify(self.repo, payload)["status"])

    def test_branch_advance_requires_reconciliation(self) -> None:
        payload = emit(self.repo, 709, "epoch-709")
        (self.repo / "file.txt").write_text("changed\n")
        self.run_git("add", ".")
        self.run_git("commit", "-qm", "new head")
        with self.assertRaisesRegex(HandoffError, "head"):
            verify(self.repo, payload)

    def test_changed_dirty_worktree_requires_reconciliation(self) -> None:
        payload = emit(self.repo, 709, "epoch-709")
        (self.repo / "new-file.txt").write_text("new")
        with self.assertRaisesRegex(HandoffError, "worktree_status"):
            verify(self.repo, payload)

    def test_wrong_worktree_is_not_same_continuation(self) -> None:
        payload = emit(self.repo, 709, "epoch-709")
        other = Path(self.temp.name) / "other"
        subprocess.run(["git", "clone", "-q", "-b", "work", str(self.remote), str(other)], check=True)
        with self.assertRaisesRegex(HandoffError, "worktree"):
            verify(other, payload)


if __name__ == "__main__":
    unittest.main()
