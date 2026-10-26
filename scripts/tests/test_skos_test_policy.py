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
        (root / "lib/ithkuil/src/skos/notation.py").write_text("VALUE = 1\n")
        (root / "lib/ithkuil/tests/test_skos_notation.py").write_text(
            "FIXTURE = 'fixtures/notation.json'\n")
        (root / "lib/ithkuil/tests/test_skos_canonical.py").write_text("")
        (root / "lib/ithkuil/tests/test_skos_identity.py").write_text("")
        (root / "lib/ithkuil/tests/test_skos_shapes.py").write_text("")
        (root / "lib/ithkuil/tests/fixtures/notation.json").write_text('{"ok": true}\n')
        (root / "lib/ithkuil/_data/source.csv").write_text("id,value\n1,x\n")
        (root / "scripts/run_tests.py").write_text("RUNNER = 1\n")
        (root / "scripts/skos_test_policy.py").write_text("POLICY = 1\n")
        return root

    def test_exact_verified_bundle_is_unchanged_and_one_byte_invalidates_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            digest, files, total_bytes = skos_test_policy.bundle_fingerprint(root)
            receipt = root / "docs/evidence/development/skos_test_bundle_v1.json"
            receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps({
                "schema": skos_test_policy.RECEIPT_SCHEMA,
                "sha256": digest,
                "file_count": files,
                "byte_count": total_bytes,
            }))
            status = skos_test_policy.bundle_status(root, receipt)
            self.assertTrue(status.verified)
            self.assertEqual(status.sha256, digest)

            (root / "lib/ithkuil/src/skos/notation.py").write_text("VALUE = 2\n")
            self.assertFalse(skos_test_policy.bundle_status(root, receipt).verified)

    def test_test_only_change_is_part_of_the_bundle_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            before, _, _ = skos_test_policy.bundle_fingerprint(root)
            (root / "lib/ithkuil/tests/test_skos_notation.py").write_text(
                "FIXTURE = 'fixtures/notation.json'\n# stronger assertion\n")
            after, _, _ = skos_test_policy.bundle_fingerprint(root)
            self.assertNotEqual(before, after)

    def test_direct_source_change_selects_owner_plus_canaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            plan = skos_test_policy.classify_changes(
                root, ("lib/ithkuil/src/skos/notation.py",))
            self.assertEqual(plan.action, "DIFF")
            self.assertIn("lib/ithkuil/tests/test_skos_notation.py", plan.tests)
            for canary in skos_test_policy.CANARY_TESTS:
                self.assertIn(canary, plan.tests)

    def test_fixture_change_selects_tests_that_reference_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            plan = skos_test_policy.classify_changes(
                root, ("lib/ithkuil/tests/fixtures/notation.json",))
            self.assertEqual(plan.action, "DIFF")
            self.assertIn("lib/ithkuil/tests/test_skos_notation.py", plan.tests)

    def test_corpus_or_cross_cutting_policy_change_requires_full_suite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            for path in (
                "lib/ithkuil/_data/source.csv",
                "lib/ithkuil/src/skos/canonical.py",
                "scripts/skos_test_policy.py",
                "docs/evidence/development/skos_test_bundle_v1.json",
            ):
                with self.subTest(path=path):
                    self.assertEqual(
                        skos_test_policy.classify_changes(root, (path,)).action,
                        "FULL")

    def test_unknown_bundle_change_fails_safe_to_full(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._root(temporary)
            (root / "lib/ithkuil/src/skos/new_surface.py").write_text("")
            plan = skos_test_policy.classify_changes(
                root, ("lib/ithkuil/src/skos/new_surface.py",))
            self.assertEqual(plan.action, "FULL")


if __name__ == "__main__":
    unittest.main()
