"""Facade and direct-CLI compatibility tests for the SKOS policy entrypoint."""
from pathlib import Path
import subprocess
import sys
import unittest

from scripts import skos_test_policy
from scripts.quality import skos_test_bundle, skos_test_selection


ROOT = Path(__file__).resolve().parents[2]


class SkosTestPolicyFacadeTests(unittest.TestCase):
    def test_public_api_reexports_split_owners(self):
        self.assertIs(skos_test_policy.BundleStatus, skos_test_bundle.BundleStatus)
        self.assertIs(skos_test_policy.TestPlan, skos_test_selection.TestPlan)
        self.assertIs(skos_test_policy.bundle_fingerprint, skos_test_bundle.bundle_fingerprint)
        self.assertIs(skos_test_policy.bundle_status, skos_test_bundle.bundle_status)
        self.assertIs(skos_test_policy.classify_changes, skos_test_selection.classify_changes)
        self.assertIs(skos_test_policy.write_receipt, skos_test_bundle.write_receipt)

    def test_direct_cli_import_path_still_works(self):
        result = subprocess.run(
            [sys.executable, "-B", "scripts/skos_test_policy.py", "--help"],
            cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("write-receipt", result.stdout)


if __name__ == "__main__":
    unittest.main()
