"""Executable contract tests for the ratified anti-monolith thresholds."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / "check_module_size.py"
spec = importlib.util.spec_from_file_location("check_module_size", SCRIPT)
check = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check
spec.loader.exec_module(check)


class DevelopmentStructureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bilqis-structure-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Fixture"], cwd=self.root, check=True)
        self.old_root = check.ROOT
        check.ROOT = self.root
        self.addCleanup(setattr, check, "ROOT", self.old_root)

    def write(self, path: str, lines: int) -> Path:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x = 1\n" * lines, encoding="utf-8")
        return target

    def commit_all(self) -> str:
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=self.root, check=True)
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip()

    def staged_problems(self):
        changes = check.changed_paths(staged=True)
        return check.violations(changes, base_ref="HEAD", staged=True)

    def test_explicit_file_trigger_is_strictly_greater_than_360(self):
        self.write("pkg/at_limit.py", 360)
        self.write("pkg/over.py", 361)
        self.assertEqual(check.explicit_violations(["pkg/at_limit.py"]), [])
        self.assertIn("target=<240", check.explicit_violations(["pkg/over.py"])[0])

    def test_encountered_legacy_file_must_finish_below_240(self):
        self.write("pkg/module.py", 400)
        self.commit_all()
        self.write("pkg/module.py", 250)
        subprocess.run(["git", "add", "pkg/module.py"], cwd=self.root, check=True)
        self.assertIn("FILE_REFACTOR_REQUIRED", self.staged_problems()[0])
        self.write("pkg/module.py", 239)
        subprocess.run(["git", "add", "pkg/module.py"], cwd=self.root, check=True)
        self.assertEqual(self.staged_problems(), [])

    def test_causing_file_to_cross_trigger_requires_full_remediation(self):
        self.write("pkg/module.py", 360)
        self.commit_all()
        self.write("pkg/module.py", 361)
        subprocess.run(["git", "add", "pkg/module.py"], cwd=self.root, check=True)
        self.assertTrue(any(item.startswith("FILE_REFACTOR_REQUIRED") for item in self.staged_problems()))

    def test_directory_trigger_requires_original_directory_to_reach_12(self):
        for index in range(18):
            self.write(f"pkg/m{index}.py", 1)
        self.commit_all()
        for index in range(5):
            target = self.root / f"pkg/m{index}.py"
            target.unlink()
            moved = self.root / "pkg" / "parts" / f"m{index}.py"
            moved.parent.mkdir(exist_ok=True)
            moved.write_text("x = 1\n")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        problems = self.staged_problems()
        self.assertTrue(any("DIRECTORY_REFACTOR_REQUIRED pkg" in item and "current=13" in item for item in problems))
        target = self.root / "pkg/m5.py"
        target.unlink()
        moved = self.root / "pkg/parts/m5.py"
        moved.write_text("x = 1\n")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        self.assertFalse(any("DIRECTORY_REFACTOR_REQUIRED pkg" in item for item in self.staged_problems()))

    def test_new_subdirectory_is_not_recursively_swept_during_same_change(self):
        self.write("anchor.py", 1)
        self.commit_all()
        for index in range(20):
            self.write(f"new_compartment/m{index}.py", 1)
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        self.assertFalse(any("DIRECTORY_REFACTOR_REQUIRED new_compartment" in item for item in self.staged_problems()))

    def test_external_vendor_code_is_not_project_authored(self):
        self.write("vendor/library/huge.py", 500)
        self.assertEqual(check.explicit_violations(["vendor/library/huge.py"]), [])


if __name__ == "__main__":
    unittest.main()
