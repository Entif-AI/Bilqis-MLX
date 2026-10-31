import json
from pathlib import Path
import tempfile
import unittest

from scripts import skos_test_policy


class SkosTestPolicyTests(unittest.TestCase):
    def _root(self, temporary):
        root = Path(temporary)
        (root / "lib/ithkuil/src/skos").mkdir(parents=True)
        (root / "lib/ithkuil/_data").mkdir(parents=True)
        (root / "lib/ithkuil/tests/fixtures").mkdir(parents=True)
        (root / "scripts").mkdir(exist_ok=True)
        (root / "skills/ithkuil-ingestion").mkdir(parents=True)
        (root / "docs/evidence/development").mkdir(parents=True)
        (root / ".github/workflows").mkdir(parents=True)

        (root / "lib/ithkuil/src/__init__.py").write_text("")
        (root / "lib/ithkuil/src/skos/__init__.py").write_text("")
        (root / "lib/ithkuil/src/skos/shared.py").write_text("VALUE = 1\n")
        (root / "lib/ithkuil/src/skos/notation.py").write_text(
            "from .shared import VALUE\nNOTATION = VALUE\n")
        (root / "lib/ithkuil/tests/test_skos_notation.py").write_text(
            "from lib.ithkuil.src.skos.notation import NOTATION\n"
            "FIXTURE = 'fixtures/notation.json'\n")
        for name in ("canonical", "identity", "shapes", "alpha", "beta", "gamma"):
            (root / f"lib/ithkuil/tests/test_skos_{name}.py").write_text(
                f"VALUE = '{name}'\n")
        (root / "lib/ithkuil/tests/helpers.py").write_text("from lib.ithkuil.src.skos.shared import VALUE\n")
        (root / "lib/ithkuil/tests/test_skos_alpha.py").write_text(
            "from lib.ithkuil.tests.helpers import VALUE\n")
        (root / "lib/ithkuil/tests/fixtures/notation.json").write_text('{"ok": true}\n')
        (root / "lib/ithkuil/_data/source.csv").write_text("id,value\n1,x\n")
        (root / "scripts/run_tests.py").write_text("RUNNER = 1\n")
        (root / "scripts/skos_test_policy.py").write_text("POLICY = 1\n")
        (root / ".github/workflows/quality.yml").write_text("name: test\n")
        return root

    def _write_current_receipt(self, root):
        digest, files, total_bytes = skos_test_policy.bundle_fingerprint(root)
        receipt = root / skos_test_policy.RECEIPT_PATH
        receipt.write_text(json.dumps({
            "schema": skos_test_policy.RECEIPT_SCHEMA,
            "sha256": digest,
            "file_count": files,
            "byte_count": total_bytes,
        }))
        return digest

    def test_receipt_checks_digest_file_count_and_byte_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            digest = self._write_current_receipt(root)
            status = skos_test_policy.bundle_status(root)
            self.assertTrue(status.verified)
            self.assertEqual(status.sha256, digest)

            receipt = json.loads((root / skos_test_policy.RECEIPT_PATH).read_text())
            receipt["file_count"] += 1
            (root / skos_test_policy.RECEIPT_PATH).write_text(json.dumps(receipt))
            status = skos_test_policy.bundle_status(root)
            self.assertFalse(status.verified)
            self.assertEqual(status.reason, "BUNDLE_FILE_COUNT_CHANGED")

            self._write_current_receipt(root)
            receipt = json.loads((root / skos_test_policy.RECEIPT_PATH).read_text())
            receipt["byte_count"] += 1
            (root / skos_test_policy.RECEIPT_PATH).write_text(json.dumps(receipt))
            status = skos_test_policy.bundle_status(root)
            self.assertFalse(status.verified)
            self.assertEqual(status.reason, "BUNDLE_BYTE_COUNT_CHANGED")

    def test_unrelated_change_skips_even_if_receipt_is_stale(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            (root / skos_test_policy.RECEIPT_PATH).write_text(json.dumps({
                "schema": skos_test_policy.RECEIPT_SCHEMA,
                "sha256": "stale",
                "file_count": 0,
                "byte_count": 0,
            }))
            plan = skos_test_policy.plan_for_changes(
                root, ("bilqis_mlx/runtime/foo.py",))
            self.assertEqual(plan.action, "SKIP")
            self.assertEqual(plan.reason, "NO_SEMANTIC_PROFILE_CHANGES")

    def test_semantic_change_requires_current_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            (root / skos_test_policy.RECEIPT_PATH).write_text(json.dumps({
                "schema": skos_test_policy.RECEIPT_SCHEMA,
                "sha256": "stale",
                "file_count": 0,
                "byte_count": 0,
            }))
            plan = skos_test_policy.plan_for_changes(
                root, ("lib/ithkuil/src/skos/notation.py",))
            self.assertEqual(plan.action, "ERROR")
            self.assertIn("SEMANTIC_RECEIPT_NOT_CURRENT", plan.reason)

    def test_direct_and_transitive_source_changes_select_owners_plus_canaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            self._write_current_receipt(root)
            direct = skos_test_policy.classify_changes(
                root, ("lib/ithkuil/src/skos/notation.py",))
            transitive = skos_test_policy.classify_changes(
                root, ("lib/ithkuil/src/skos/shared.py",))
            for plan in (direct, transitive):
                self.assertEqual(plan.action, "DIFF")
                self.assertIn("lib/ithkuil/tests/test_skos_notation.py", plan.tests)
                for canary in skos_test_policy.CANARY_TESTS:
                    self.assertIn(canary, plan.tests)
            self.assertIn("lib/ithkuil/tests/test_skos_alpha.py", transitive.tests)

    def test_fixture_and_test_support_changes_select_consumers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            fixture = skos_test_policy.classify_changes(
                root, ("lib/ithkuil/tests/fixtures/notation.json",))
            helper = skos_test_policy.classify_changes(
                root, ("lib/ithkuil/tests/helpers.py",))
            self.assertEqual(fixture.action, "DIFF")
            self.assertIn("lib/ithkuil/tests/test_skos_notation.py", fixture.tests)
            self.assertEqual(helper.action, "DIFF")
            self.assertIn("lib/ithkuil/tests/test_skos_alpha.py", helper.tests)

    def test_cross_cutting_policy_corpus_unknown_and_receipt_only_changes_are_full(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            (root / "lib/ithkuil/src/skos/new_surface.py").write_text("")
            cases = {
                "lib/ithkuil/_data/source.csv": "CANONICAL_CORPUS_CHANGED",
                "lib/ithkuil/src/skos/canonical.py": "CROSS_CUTTING_MODULE_CHANGED:canonical",
                "scripts/skos_test_policy.py": "TEST_POLICY_CHANGED",
                str(skos_test_policy.RECEIPT_PATH): "RECEIPT_ONLY_CHANGED",
                "lib/ithkuil/src/skos/new_surface.py": "UNKNOWN_SKOS_OWNER:lib/ithkuil/src/skos/new_surface.py",
            }
            for path, reason in cases.items():
                with self.subTest(path=path):
                    plan = skos_test_policy.classify_changes(root, (path,))
                    self.assertEqual(plan.action, "FULL")
                    self.assertEqual(plan.reason, reason)

    def test_current_receipt_allows_bounded_semantic_diff(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            self._write_current_receipt(root)
            plan = skos_test_policy.plan_for_changes(
                root, ("lib/ithkuil/src/skos/notation.py",))
            self.assertEqual(plan.action, "DIFF")
            self.assertIn("lib/ithkuil/tests/test_skos_notation.py", plan.tests)

    def test_policy_helper_change_is_full_without_receipt_refresh(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            self._write_current_receipt(root)
            plan = skos_test_policy.plan_for_changes(
                root, ("scripts/skos_policy/impact.py",))
            self.assertEqual(plan.action, "FULL")
            self.assertEqual(plan.reason, "TEST_POLICY_CHANGED")

    def test_forced_exhaustive_ignores_differential_classification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            plan = skos_test_policy.plan_for_changes(
                root, ("bilqis_mlx/runtime/foo.py",), force_full=True)
            self.assertEqual(plan.action, "FULL")
            self.assertEqual(plan.reason, "FORCED_EXHAUSTIVE")

    def test_full_shards_are_deterministic_complete_and_non_overlapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            first = skos_test_policy.full_test_shards(root, 3)
            second = skos_test_policy.full_test_shards(root, 3)
            self.assertEqual(first, second)
            flattened = [test for shard in first for test in shard]
            expected = list(skos_test_policy.semantic_test_files(root))
            self.assertEqual(sorted(flattened), expected)
            self.assertEqual(len(flattened), len(set(flattened)))
            self.assertTrue(all(shard for shard in first))


if __name__ == "__main__":
    unittest.main()
