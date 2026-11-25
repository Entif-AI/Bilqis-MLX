"""The readiness projection has an exact and narrow content boundary."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.quality.verification_projection import prepare, validate_projection


class VerificationProjectionTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {
            key: value for key, value in os.environ.items() if not key.startswith("GIT_")
        }, clear=True))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "repo"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.test")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root)

    def commit(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        self.git("add", name)
        self.git("commit", "-qm", "fixture")

    def test_excluded_changes_reuse_exact_projection(self):
        self.commit("apps/mission-control/view.js", "const x = 1;")
        self.commit("docs/evidence/development/report.md", "report")
        self.commit("bilqis_mlx/subject.py", "x = 1")
        source = self.root.parent / "projection"
        self.assertTrue(prepare(self.root, source))
        self.assertFalse((source / "apps/mission-control").exists())
        self.assertFalse((source / "docs/evidence/development").exists())
        self.assertFalse((source / ".git").exists())
        original = validate_projection(self.root, source)
        self.assertIsNotNone(original)
        self.commit("apps/mission-control/view.js", "const x = 2;")
        self.assertEqual(validate_projection(self.root, source), original)
        self.commit("bilqis_mlx/subject.py", "x = 2")
        self.assertIsNone(validate_projection(self.root, source))

    def test_changed_or_unexpected_snapshot_bytes_reject(self):
        self.commit("subject.py", "x = 1")
        source = self.root.parent / "projection"
        self.assertTrue(prepare(self.root, source))
        (source / "subject.py").write_text("x = 2")
        self.assertIsNone(validate_projection(self.root, source))
        (source / "subject.py").write_text("x = 1")
        (source / "unexpected.py").write_text("x = 3")
        self.assertIsNone(validate_projection(self.root, source))
        (source / "unexpected.py").unlink()
        (source / "unexpected").mkdir()
        self.assertIsNone(validate_projection(self.root, source))


if __name__ == "__main__":
    unittest.main()
