import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import differential_test_gate as gate


class DifferentialTestGateTests(unittest.TestCase):
    def _repo(self) -> tempfile.TemporaryDirectory:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
        (root / ".gitignore").write_text(".local/\n")
        (root / "pkg").mkdir()
        (root / "pkg" / "thing.py").write_text("VALUE = 1\n")
        tests = root / "pkg" / "tests"
        tests.mkdir()
        (tests / "test_thing.py").write_text("from pkg.thing import VALUE\n")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
        return temporary

    def test_fresh_worktree_baseline_is_current_head_not_parent_commit(self):
        temporary = self._repo()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "pkg" / "thing.py").write_text("VALUE = 2\n")
        subprocess.run(["git", "commit", "-qam", "change"], cwd=root, check=True)

        self.assertEqual(gate.resolve_test_base(root), "HEAD")

    def test_last_passing_head_becomes_next_commit_test_base(self):
        temporary = self._repo()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        passing_head = gate.git(root, "rev-parse", "HEAD")
        receipt = gate.Receipt(
            gate="leaf",
            fingerprint=gate.workspace_fingerprint(root),
            head=passing_head,
            base_ref="HEAD",
            command=["pytest"],
            passed=True,
        )
        gate.write_receipt(root, receipt)
        (root / "pkg" / "thing.py").write_text("VALUE = 2\n")
        subprocess.run(["git", "commit", "-qam", "change"], cwd=root, check=True)

        self.assertEqual(gate.resolve_test_base(root), passing_head)

    def test_explicit_test_base_is_independent_of_quality_base(self):
        temporary = self._repo()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)

        self.assertEqual(
            gate.resolve_test_base(root, environ={
                "BILQIS_QUALITY_BASE_REF": "distant-quality-base",
                "BILQIS_TEST_BASE_REF": "HEAD",
            }),
            "HEAD",
        )

    def test_cold_plan_selects_direct_owner_tests(self):
        temporary = self._repo()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "pkg" / "thing.py").write_text("VALUE = 2\n")

        plan = gate.plan_leaf(root, base_ref="HEAD")

        self.assertEqual(plan.mode, "cold-targeted")
        self.assertEqual(plan.tests, ("pkg/tests/test_thing.py",))

    def test_warm_testmon_plan_remains_bounded_to_owner_tests(self):
        temporary = self._repo()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "pkg" / "thing.py").write_text("VALUE = 2\n")
        (root / gate.TESTMON_DATA).write_bytes(b"warm-marker")

        plan = gate.plan_leaf(root, base_ref="HEAD")

        self.assertEqual(plan.mode, "testmon-targeted")
        self.assertEqual(plan.tests, ("pkg/tests/test_thing.py",))

    def test_docs_only_change_skips_python_tests(self):
        temporary = self._repo()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "README.md").write_text("docs only\n")

        plan = gate.plan_leaf(root, base_ref="HEAD")

        self.assertEqual(plan.mode, "skip")
        self.assertEqual(plan.tests, ())

    def test_matching_success_receipt_reuses_without_rerun(self):
        temporary = self._repo()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        fingerprint = gate.workspace_fingerprint(root)
        receipt = gate.Receipt(
            gate="leaf",
            fingerprint=fingerprint,
            head=gate.git(root, "rev-parse", "HEAD"),
            base_ref="HEAD^1",
            command=["pytest"],
            passed=True,
        )
        gate.write_receipt(root, receipt)

        loaded = gate.read_receipt(root, "leaf")

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.fingerprint, fingerprint)
        self.assertTrue(gate.receipt_reusable(root, loaded))

    def test_dirty_file_invalidates_success_receipt(self):
        temporary = self._repo()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        receipt = gate.Receipt(
            gate="leaf",
            fingerprint=gate.workspace_fingerprint(root),
            head=gate.git(root, "rev-parse", "HEAD"),
            base_ref="HEAD^1",
            command=["pytest"],
            passed=True,
        )
        gate.write_receipt(root, receipt)
        (root / "pkg" / "thing.py").write_text("VALUE = 3\n")

        self.assertFalse(gate.receipt_reusable(root, gate.read_receipt(root, "leaf")))

    def test_receipt_is_local_ignored_state(self):
        temporary = self._repo()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        receipt = gate.Receipt(
            gate="leaf",
            fingerprint=gate.workspace_fingerprint(root),
            head=gate.git(root, "rev-parse", "HEAD"),
            base_ref="HEAD^1",
            command=["pytest"],
            passed=True,
        )
        gate.write_receipt(root, receipt)
        path = root / gate.RECEIPT_DIR / "leaf.json"

        self.assertTrue(path.exists())
        self.assertEqual(json.loads(path.read_text())["gate"], "leaf")


if __name__ == "__main__":
    unittest.main()
