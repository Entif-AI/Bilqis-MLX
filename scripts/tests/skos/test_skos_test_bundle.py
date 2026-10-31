"""Bundle identity tests for scripts.quality.skos_test_bundle."""
import json
import tempfile
import unittest

from scripts.quality import skos_test_bundle
from scripts.tests.skos.policy_fixture import SkosPolicyFixture


class SkosTestBundleTests(SkosPolicyFixture, unittest.TestCase):
    def test_exact_verified_bundle_is_unchanged_and_one_byte_invalidates_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.root(temporary)
            digest, files, total_bytes = skos_test_bundle.bundle_fingerprint(root)
            receipt = root / skos_test_bundle.RECEIPT_PATH
            receipt.parent.mkdir(parents=True)
            receipt.write_text(json.dumps({
                "schema": skos_test_bundle.RECEIPT_SCHEMA,
                "sha256": digest,
                "file_count": files,
                "byte_count": total_bytes,
            }))
            status = skos_test_bundle.bundle_status(root, receipt)
            self.assertTrue(status.verified)
            self.assertEqual(status.sha256, digest)

            (root / "lib/ithkuil/src/skos/notation.py").write_text("VALUE = 2\n")
            self.assertFalse(skos_test_bundle.bundle_status(root, receipt).verified)

    def test_test_only_change_is_part_of_the_bundle_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.root(temporary)
            before, _, _ = skos_test_bundle.bundle_fingerprint(root)
            (root / "lib/ithkuil/tests/skos/core_identity/test_skos_notation.py").write_text(
                "FIXTURE = 'fixtures/notation.json'\n# stronger assertion\n")
            after, _, _ = skos_test_bundle.bundle_fingerprint(root)
            self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
