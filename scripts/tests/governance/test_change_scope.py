"""Temporal adoption tests for anti-monolith change scoping."""
from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.quality import change_scope


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


class ChangeScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bilqis-change-scope-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Fixture"], cwd=self.root, check=True)
        (self.root / "root.txt").write_text("root\n")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "root"], cwd=self.root, check=True)
        self.root_sha = git(self.root, "rev-parse", "HEAD")
        self.old_adoption = change_scope.GOVERNANCE_ADOPTION_COMMIT
        self.addCleanup(setattr, change_scope, "GOVERNANCE_ADOPTION_COMMIT", self.old_adoption)

    def commit_file(self, name: str, text: str, message: str) -> str:
        (self.root / name).write_text(text)
        subprocess.run(["git", "add", name], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", message], cwd=self.root, check=True)
        return git(self.root, "rev-parse", "HEAD")

    def test_long_lived_branch_starts_enforcement_at_adoption_merge(self):
        subprocess.run(["git", "branch", "feature", self.root_sha], cwd=self.root, check=True)
        adoption = self.commit_file("governance.txt", "rule\n", "governance")
        change_scope.GOVERNANCE_ADOPTION_COMMIT = adoption
        main_head = self.commit_file("main.txt", "main\n", "main followup")
        subprocess.run(["git", "switch", "-q", "feature"], cwd=self.root, check=True)
        legacy = self.commit_file("legacy.py", "VALUE = 1\n", "legacy feature")
        subprocess.run(["git", "merge", "--no-ff", "-qm", "adopt governance", "main"], cwd=self.root, check=True)
        self.commit_file("post.py", "VALUE = 2\n", "post adoption")
        self.assertEqual(change_scope.effective_base(self.root, main_head), legacy)

    def test_branch_created_after_adoption_uses_normal_merge_base(self):
        adoption = self.commit_file("governance.txt", "rule\n", "governance")
        change_scope.GOVERNANCE_ADOPTION_COMMIT = adoption
        main_head = self.commit_file("main.txt", "main\n", "main followup")
        subprocess.run(["git", "switch", "-qc", "feature"], cwd=self.root, check=True)
        self.commit_file("feature.py", "VALUE = 3\n", "feature")
        self.assertEqual(change_scope.effective_base(self.root, main_head), main_head)


if __name__ == "__main__":
    unittest.main()
