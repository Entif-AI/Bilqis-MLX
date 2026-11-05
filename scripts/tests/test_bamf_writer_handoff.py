from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

from scripts.bamf import writer_handoff
from scripts.bamf.writer_handoff import HandoffError, emit, verify
from scripts.tests.bamf_handoff.fixtures import WriterHandoffFixture


class WriterHandoffTests(WriterHandoffFixture):
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

    def test_local_only_branch_preserves_dirty_evidence_without_remote_match(self) -> None:
        self.run_git("switch", "-c", "local-only")
        local = self.repo / "local.txt"
        local.write_text("preserved draft\n")
        payload = emit(self.repo, 829, "epoch-829")
        self.assertEqual("local-only", payload["branch"])
        self.assertEqual(str(self.repo.resolve()), payload["worktree"])
        self.assertIsNone(payload["upstream"])
        self.assertIsNone(payload["observed_remote_head"])
        self.assertEqual("UNVERIFIED", payload["status"])
        self.assertEqual("NO_UPSTREAM", payload["reason"])
        self.assertEqual("UNVERIFIED", verify(self.repo, payload)["status"])
        local.write_text("changed draft\n")
        with self.assertRaisesRegex(HandoffError, "worktree_status"):
            verify(self.repo, payload)

    def test_adding_upstream_to_local_snapshot_requires_reconciliation(self) -> None:
        self.run_git("switch", "-c", "local-only")
        payload = emit(self.repo, 829, "epoch-829")
        self.run_git("branch", "--set-upstream-to=origin/work")
        with self.assertRaisesRegex(HandoffError, "upstream"):
            verify(self.repo, payload)

    def test_local_only_cli_emits_json_but_verification_is_not_success(self) -> None:
        self.run_git("switch", "-c", "local-only")
        script = Path(__file__).resolve().parents[1] / "bamf/writer_handoff.py"
        command = [sys.executable, str(script), "--worktree", str(self.repo)]
        emitted = subprocess.run(
            [*command, "emit", "--issue", "829", "--epoch", "epoch-829"],
            capture_output=True, text=True, check=True,
        )
        payload = json.loads(emitted.stdout)
        saved = Path(self.temp.name) / "handoff.json"
        saved.write_text(emitted.stdout)
        result = subprocess.run(
            [*command, "verify", "--payload", str(saved)],
            capture_output=True, text=True,
        )
        self.assertEqual(2, result.returncode)
        self.assertEqual("UNVERIFIED", json.loads(result.stdout)["status"])
        self.assertEqual(payload["head"], json.loads(result.stdout)["head"])

    def test_unfetched_remote_advance_still_requires_reconciliation(self) -> None:
        payload = emit(self.repo, 829, "epoch-829")
        other = Path(self.temp.name) / "other"
        subprocess.run(["git", "clone", "-q", "-b", "work", str(self.remote), str(other)], check=True)
        for args in (("config", "user.email", "test@example.invalid"),
                     ("config", "user.name", "Test")):
            subprocess.run(["git", *args], cwd=other, check=True)
        (other / "file.txt").write_text("remote change\n")
        for args in (("add", "."), ("commit", "-qm", "remote advance"),
                     ("push", "-q", "origin", "work")):
            subprocess.run(["git", *args], cwd=other, check=True)
        with self.assertRaisesRegex(HandoffError, "remote changed after last fetch"):
            verify(self.repo, payload)

    def test_untracked_symlink_retargeting_requires_reconciliation(self) -> None:
        self.run_git("switch", "-c", "local-only")
        for kind in ("dangling", "directory", "file"):
            with self.subTest(kind=kind):
                targets = [Path(self.temp.name) / f"{kind}-{side}" for side in ("left", "right")]
                for target in targets:
                    if kind == "directory":
                        target.mkdir()
                    elif kind == "file":
                        target.write_text("same referent bytes\n")
                link = self.repo / f"draft-{kind}-link"
                link.symlink_to(targets[0])
                payload = emit(self.repo, 831, "epoch-829")
                self.assertEqual("UNVERIFIED", verify(self.repo, payload)["status"])
                link.unlink()
                link.symlink_to(targets[1])
                with self.assertRaisesRegex(HandoffError, "worktree_status"):
                    verify(self.repo, payload)
                link.unlink()

    def test_untracked_symlink_and_file_bytes_cannot_alias(self) -> None:
        for first in ("symlink", "file"):
            with self.subTest(first=first):
                path = self.repo / f"draft-{first}"
                if first == "symlink":
                    path.symlink_to("target")
                else:
                    path.write_bytes(b"symlink\0target")
                payload = emit(self.repo, 832, "epoch-829")
                self.assertEqual("CONTINUATION_MATCH", verify(self.repo, payload)["status"])
                path.unlink()
                if first == "file":
                    path.symlink_to("target")
                else:
                    path.write_bytes(b"symlink\0target")
                with self.assertRaisesRegex(HandoffError, "worktree_status"):
                    verify(self.repo, payload)

    def test_untracked_executable_mode_change_requires_reconciliation(self) -> None:
        path = self.repo / "script"
        path.write_text("unchanged bytes\n")
        path.chmod(0o644)
        payload = emit(self.repo, 832, "epoch-829")
        path.chmod(0o755)
        with self.assertRaisesRegex(HandoffError, "worktree_status"):
            verify(self.repo, payload)

    def test_unsupported_untracked_entry_cannot_issue_a_snapshot(self) -> None:
        path = self.repo / "pipe"
        path.write_text("enumerated as a regular file\n")
        read_git = writer_handoff.git

        def replace_after_enumeration(root, *args):
            result = read_git(root, *args)
            if args[0] == "ls-files" and "--others" in args:
                path.unlink()
                os.mkfifo(path)
            return result

        with patch.object(writer_handoff, "git", side_effect=replace_after_enumeration):
            with self.assertRaisesRegex(HandoffError, "unsupported captured entry"):
                emit(self.repo, 832, "epoch-829")

    def blob(self, content: str) -> str:
        return subprocess.run(["git", "hash-object", "-w", "--stdin"],
                              cwd=self.repo, input=content, text=True,
                              capture_output=True, check=True).stdout.strip()

    def test_index_only_content_change_cannot_hide_behind_same_worktree(self) -> None:
        path = self.repo / "file.txt"
        path.write_text("staged B\n")
        self.run_git("add", "file.txt")
        path.write_text("worktree C\n")
        payload = emit(self.repo, 834, "epoch-829")
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=self.repo)
        self.run_git("update-index", "--cacheinfo", "100644", self.blob("staged D\n"), "file.txt")
        self.assertEqual("worktree C\n", path.read_text())
        self.assertEqual(status, subprocess.check_output(["git", "status", "--porcelain"], cwd=self.repo))
        with self.assertRaisesRegex(HandoffError, "worktree_status"):
            verify(self.repo, payload)

    def test_changed_unmerged_index_stage_requires_reconciliation(self) -> None:
        base, first, second = (self.blob(text) for text in ("base\n", "ours B\n", "ours D\n"))

        def stages(ours):
            data = ("0 " + "0" * 40 + "\tfile.txt\n" +
                    f"100644 {base} 1\tfile.txt\n100644 {ours} 2\tfile.txt\n" +
                    f"100644 {base} 3\tfile.txt\n")
            subprocess.run(["git", "update-index", "--index-info"], cwd=self.repo,
                           input=data, text=True, capture_output=True, check=True)

        stages(first)
        payload = emit(self.repo, 834, "epoch-829")
        stages(second)
        with self.assertRaisesRegex(HandoffError, "worktree_status"):
            verify(self.repo, payload)

    def test_index_flag_change_requires_reconciliation(self) -> None:
        payload = emit(self.repo, 834, "epoch-829")
        self.run_git("update-index", "--assume-unchanged", "file.txt")
        with self.assertRaisesRegex(HandoffError, "worktree_status"):
            verify(self.repo, payload)

    def test_existing_suppression_flags_cannot_hide_tracked_content_edits(self) -> None:
        path = self.repo / "file.txt"
        for flag in ("assume-unchanged", "skip-worktree"):
            with self.subTest(flag=flag):
                self.run_git("update-index", "--" + flag, "file.txt")
                payload = emit(self.repo, 835, "epoch-829")
                self.assertEqual("CONTINUATION_MATCH", verify(self.repo, payload)["status"])
                path.write_text("hidden tracked edit\n")
                try:
                    with self.assertRaisesRegex(HandoffError, "worktree_status"):
                        verify(self.repo, payload)
                finally:
                    self.run_git("update-index", "--no-" + flag, "file.txt")
                    path.write_text("initial\n")

    def test_absent_skipped_path_restored_without_index_change_requires_reconciliation(self) -> None:
        path = self.repo / "file.txt"
        self.run_git("update-index", "--skip-worktree", "file.txt")
        path.unlink()
        payload = emit(self.repo, 835, "epoch-829")
        self.assertEqual("CONTINUATION_MATCH", verify(self.repo, payload)["status"])
        path.write_text("restored file\n")
        with self.assertRaisesRegex(HandoffError, "worktree_status"):
            verify(self.repo, payload)


if __name__ == "__main__":
    unittest.main()
