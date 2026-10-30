"""Portable package closure and execution through the extracted Skill surface."""
from __future__ import annotations
from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts.package_ithkuil_skill import stage

REPO = REPO_ROOT


class IngestionPackageTests(unittest.TestCase):
    def test_staging_contains_exact_fixture_and_no_runtime_or_corpus(self):
        with tempfile.TemporaryDirectory() as temporary:
            skill = stage(REPO, Path(temporary) / "stage")
            fixture = REPO / "lib/ithkuil/tests/fixtures/ingestion"
            bundled = skill / "assets/fixture"
            expected = {p.relative_to(fixture): p.read_bytes()
                        for p in fixture.rglob("*") if p.is_file()}
            actual = {p.relative_to(bundled): p.read_bytes()
                      for p in bundled.rglob("*") if p.is_file()}
            self.assertEqual(actual, expected)
            self.assertTrue((skill / "scripts/cleanroom.py").is_file())
            self.assertFalse((skill / "lib").exists())
            self.assertFalse((skill / "_data").exists())
            self.assertFalse((skill / "runs").exists())

    def test_staging_refuses_unintended_resources_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(REPO / "skills", root / "skills")
            fixture = root / "lib/ithkuil/tests/fixtures/ingestion"
            shutil.copytree(REPO / "lib/ithkuil/tests/fixtures/ingestion", fixture)
            unexpected = root / "skills/ithkuil-ingestion/secret.env"
            unexpected.write_text("not a credential")
            with self.assertRaises(ValueError):
                stage(root, root / "output-one")
            unexpected.unlink()
            (fixture / "unexpected.csv").write_text("not fixture input")
            with self.assertRaises(ValueError):
                stage(root, root / "output-extra-fixture")
            (fixture / "unexpected.csv").unlink()
            (fixture / "linked").symlink_to(fixture / "descriptor.json")
            with self.assertRaises(ValueError):
                stage(root, root / "output-two")

    def test_extracted_skill_reproduces_cleanroom_and_failure_isolation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staged = stage(REPO, root / "stage")
            archive = shutil.make_archive(str(root / "skill"), "zip", staged.parent, staged.name)
            shutil.unpack_archive(archive, root / "installed")
            skill = root / "installed/ithkuil-ingestion"
            completed = subprocess.run(
                [sys.executable, "-B", str(skill / "scripts/cleanroom.py"),
                 "--repo", str(REPO), "--python", sys.executable,
                 "--output-root", str(root / "proof"), "--verify-failures"],
                cwd=root, capture_output=True, text=True, timeout=180, check=False)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            proof = json.loads((root / "proof/proof.json").read_text())
            self.assertEqual(proof["differences"], [])
            self.assertEqual(proof["independent_runtime_workspaces"], 2)
            failures = json.loads((root / "proof/failure-proof.json").read_text())
            self.assertEqual(failures["source"], "BLOCKED")
            self.assertEqual(failures["semantic_failed_gates"], ["no-omission"])
            self.assertEqual(failures["required_graph"], "FAILED")
            self.assertTrue(failures["prior_authoritative_artifacts_unchanged"])


if __name__ == "__main__":
    unittest.main()
