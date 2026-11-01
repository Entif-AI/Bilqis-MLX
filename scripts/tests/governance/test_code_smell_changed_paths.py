"""Regression tests for rename-aware changed-file smell enforcement."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).parents[2] / "code_smell_audit.py"
spec = importlib.util.spec_from_file_location("code_smell_audit", SCRIPT)
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


class ChangedPathSmellTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bilqis-smell-rename-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@example.test"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Fixture"], cwd=self.root, check=True)
        self.old_root = audit.ROOT
        audit.ROOT = self.root
        self.addCleanup(setattr, audit, "ROOT", self.old_root)

    def commit(self, path: str, text: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", path], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=self.root, check=True)

    def changed_findings(self):
        base, records = audit._staged_records()
        current = audit.audit(audit._paths([new for _, _, new in records]))
        prior = {"fingerprints": [list(audit.fingerprint(item))
                                  for item in audit._base_findings(base, records)]}
        return audit.compare_to_baseline(current, prior)

    def test_explicit_empty_scope_does_not_expand_to_whole_repository(self):
        self.assertEqual(audit._paths([]), [])

    def test_staged_rename_preserves_existing_smell_identity(self):
        self.commit("old.py", "VALUES = []\n")
        subprocess.run(["git", "mv", "old.py", "new.py"], cwd=self.root, check=True)
        self.assertEqual(self.changed_findings(), [])

    def test_staged_rename_still_rejects_new_smell(self):
        self.commit("old.py", "VALUES = []\n")
        subprocess.run(["git", "mv", "old.py", "new.py"], cwd=self.root, check=True)
        (self.root / "new.py").write_text("VALUES = []\nMORE = {}\n", encoding="utf-8")
        subprocess.run(["git", "add", "new.py"], cwd=self.root, check=True)
        findings = self.changed_findings()
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][1:], ("module-mutable-literal", "MORE"))

    def test_existing_physical_owner_is_not_reported_as_new_debt(self):
        owner = "bilqis_mlx/runtime/_batch/atlas_training_adapter.py"
        self.commit(owner, "EXISTING = []\n")
        records = [("R100", "bilqis_mlx/runtime/atlas_training_adapter.py", owner)]
        prior = audit._base_findings("HEAD", records)
        expected = ("bilqis_mlx/runtime/atlas_training_adapter.py",
                    "module-mutable-literal", "EXISTING")
        self.assertEqual([audit.fingerprint(item) for item in prior], [expected])
        unchanged = audit.inspect_source(audit.logical_source_path(owner),
                                         "EXISTING = []\n")
        baseline = {"fingerprints": [list(audit.fingerprint(item)) for item in prior]}
        self.assertEqual(audit.compare_to_baseline(unchanged, baseline), [])
        introduced = audit.inspect_source(audit.logical_source_path(owner),
                                          "EXISTING = []\nNEW = {}\n")
        self.assertEqual(audit.compare_to_baseline(introduced, baseline), [
            ("bilqis_mlx/runtime/atlas_training_adapter.py",
             "module-mutable-literal", "NEW")])

    def test_ambiguous_physical_owners_do_not_hide_new_debt(self):
        self.commit("bilqis_mlx/runtime/_batch/atlas_training_adapter.py",
                    "EXISTING = []\n")
        self.commit("bilqis_mlx/runtime/_admission/atlas_training_adapter.py",
                    "EXISTING = []\n")
        records = [("R100", "bilqis_mlx/runtime/atlas_training_adapter.py",
                    "bilqis_mlx/runtime/_batch/atlas_training_adapter.py")]
        self.assertEqual(audit._base_findings("HEAD", records), [])

    def test_added_duplicate_physical_owner_cannot_inherit_existing_debt(self):
        original = "bilqis_mlx/runtime/_batch/owner.py"
        duplicate = "bilqis_mlx/runtime/_admission/owner.py"
        self.commit(original, "EXISTING = []\n")
        target = self.root / duplicate
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("EXISTING = []\n", encoding="utf-8")
        subprocess.run(["git", "add", duplicate], cwd=self.root, check=True)
        self.assertEqual(self.changed_findings(), [
            ("bilqis_mlx/runtime/owner.py", "module-mutable-literal", "EXISTING")])


if __name__ == "__main__":
    unittest.main()
