"""Disposable Git worktree proof for the reversible legacy-root cleanup."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.operations import relocate_legacy_worktrees as relocate


def git(*args):
    result = subprocess.run(("git", *map(str, args)), text=True,
                            capture_output=True, check=True)
    return result.stdout.strip()


class RelocationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bilqis-relocate-fixture-")
        self.addCleanup(self.temp.cleanup)
        home = Path(self.temp.name).resolve()
        self.code = home / "Code"
        self.archive = home / "Archives" / "Bilqis" / "worktrees"
        self.code.mkdir()
        self.repo = self.code / "Bilqis"
        git("init", "-q", "-b", "main", self.repo)
        git("-C", self.repo, "config", "user.email", "fixture@example.test")
        git("-C", self.repo, "config", "user.name", "Fixture")
        (self.repo / "README.txt").write_text("baseline\n")
        git("-C", self.repo, "add", "README.txt")
        git("-C", self.repo, "commit", "-qm", "initial")
        self.names = ("bilqis-fixture-a", "bilqis-fixture-b",
                      "bilqis-learner-custody")
        for name in self.names[:2]:
            git("-C", self.repo, "worktree", "add", "-qb", "fixture/"+name,
                self.code / name)
        (self.code / "bilqis-learner-custody").mkdir()
        (self.code / "bilqis-learner-custody" / "receipts.txt").write_text("KEEP ME\n")

    def operation(self, mode, **kw):
        return relocate.execute(mode, code=self.code, archive=self.archive,
                                names=self.names, guard=lambda paths: None, **kw)

    def test_plan_is_read_only_and_refuses_missing_confirm(self):
        self.assertEqual(self.operation("plan")["selected"], 3)
        self.assertFalse((self.archive.parent / relocate.MANIFEST_NAME).exists())
        with self.assertRaisesRegex(RuntimeError, "confirm"):
            self.operation("apply")
        self.assertFalse(self.archive.parent.exists())

    def test_round_trip_preserves_dirty_worktrees_and_standalone(self):
        path = self.code / self.names[0]
        (path / "README.txt").write_text("tracked edit\n")
        (path / "new-untracked.txt").write_text("untracked data\n")
        before = git("-C", path, "rev-parse", "HEAD")
        report = self.operation("apply", confirm=True)
        self.assertEqual(report["moves_this_invocation"], 3)
        self.assertFalse(path.exists())
        moved = self.archive / self.names[0]
        self.assertEqual(git("-C", moved, "rev-parse", "HEAD"), before)
        self.assertEqual((moved / "README.txt").read_text(), "tracked edit\n")
        self.assertEqual((moved / "new-untracked.txt").read_text(), "untracked data\n")
        self.assertEqual((self.archive / "bilqis-learner-custody" / "receipts.txt").read_text(),
                         "KEEP ME\n")
        self.assertIn(moved, relocate.registered_worktrees(self.repo))
        self.assertEqual(self.operation("apply", confirm=True)["moves_this_invocation"], 0)

        undone = self.operation("restore", confirm=True)
        self.assertEqual(undone["moves_this_invocation"], 3)
        self.assertIn(path, relocate.registered_worktrees(self.repo))
        self.assertEqual((path / "README.txt").read_text(), "tracked edit\n")
        self.assertEqual((path / "new-untracked.txt").read_text(), "untracked data\n")
        self.assertEqual((self.code / "bilqis-learner-custody" / "receipts.txt").read_text(),
                         "KEEP ME\n")
        self.assertEqual(self.operation("restore", confirm=True)["moves_this_invocation"], 0)
        data = json.loads((self.archive.parent / relocate.MANIFEST_NAME).read_text())
        self.assertTrue(all(item["location"] == "original" for item in data["items"].values()))

    def test_resume_after_move_without_manifest_update(self):
        self.operation("apply", confirm=True, chosen=(self.names[0],))
        # Simulate power loss after git worktree move and before manifest fsync.
        source = self.code / self.names[1]
        target = self.archive / self.names[1]
        git("-C", self.repo, "worktree", "move", source, target)
        state = json.loads((self.archive.parent / relocate.MANIFEST_NAME).read_text())
        self.assertEqual(state["items"][self.names[1]]["location"], "original")
        report = self.operation("apply", confirm=True)
        self.assertEqual(report["moves_this_invocation"], 1)  # custody only
        self.assertEqual(self.operation("restore", confirm=True)["moves_this_invocation"], 3)

    def test_collision_and_process_guard_fail_without_moving(self):
        (self.archive / self.names[0]).mkdir(parents=True)
        with self.assertRaisesRegex(RuntimeError, "Collision"):
            self.operation("apply", confirm=True)
        self.assertTrue((self.code / self.names[0]).exists())
        (self.archive / self.names[0]).rmdir()
        with self.assertRaisesRegex(RuntimeError, "trainer active"):
            relocate.execute("apply", code=self.code, archive=self.archive,
                             names=self.names, confirm=True,
                             guard=lambda paths: (_ for _ in ()).throw(
                                 RuntimeError("trainer active")))
        self.assertFalse((self.archive.parent / relocate.MANIFEST_NAME).exists())


if __name__ == "__main__":
    unittest.main()
