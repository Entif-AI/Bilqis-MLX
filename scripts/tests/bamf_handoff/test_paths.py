"""Rooted filesystem capture must never read symlink referents."""
import os
from pathlib import Path
from unittest.mock import patch

from scripts.bamf.writer_handoff import HandoffError, emit
from scripts.tests.bamf_handoff.fixtures import WriterHandoffFixture


class CapturedPathTests(WriterHandoffFixture):
    def test_flagged_tracked_path_rejects_symlink_ancestor(self):
        directory = self.repo / "nested"
        directory.mkdir()
        (directory / "file").write_text("inside\n")
        self.run_git("add", "nested/file")
        self.run_git("commit", "-qm", "nested source")
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (outside / "file").write_text("outside sentinel\n")
        (directory / "file").unlink()
        directory.rmdir()
        directory.symlink_to(outside)
        for flag in ("assume-unchanged", "skip-worktree"):
            with self.subTest(flag=flag):
                self.run_git("update-index", "--" + flag, "nested/file")
                try:
                    with self.assertRaisesRegex(HandoffError, "ancestor"):
                        emit(self.repo, 837, "epoch-829")
                finally:
                    self.run_git("update-index", "--no-" + flag, "nested/file")

    def replace_after_metadata(self, name, replacement):
        read_stat = os.stat
        changed = []

        def inspect(path, *args, **kwargs):
            metadata = read_stat(path, *args, **kwargs)
            if path == name and "dir_fd" in kwargs and not changed:
                replacement()
                changed.append(True)
            return metadata

        return inspect, changed

    def test_leaf_becoming_symlink_before_open_rejects(self):
        outside = Path(self.temp.name) / "outside-file"
        outside.write_text("outside sentinel\n")
        path = self.repo / "file.txt"
        self.run_git("update-index", "--assume-unchanged", "file.txt")

        def replace():
            path.unlink()
            path.symlink_to(outside)

        inspect, changed = self.replace_after_metadata("file.txt", replace)
        with patch("scripts.bamf.writer_handoff.os.stat", side_effect=inspect):
            with self.assertRaisesRegex(HandoffError, "changed"):
                emit(self.repo, 837, "epoch-829")
        self.assertEqual([True], changed)

    def test_leaf_becoming_fifo_before_open_rejects_without_reading(self):
        path = self.repo / "race"
        path.write_text("regular input\n")

        def replace():
            path.unlink()
            os.mkfifo(path)

        inspect, changed = self.replace_after_metadata("race", replace)
        with patch("scripts.bamf.writer_handoff.os.stat", side_effect=inspect):
            with self.assertRaisesRegex(HandoffError, "unsupported captured entry"):
                emit(self.repo, 837, "epoch-829")
        self.assertEqual([True], changed)
