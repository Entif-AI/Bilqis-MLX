"""Installed artifact identity, local ledger trust and cold retries."""
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.quality.verification_environment import installed_identity
from scripts.quality.verification_ledger import VerificationLedger, full_requested


class VerificationEnvironmentTests(unittest.TestCase):
    def test_same_version_artifact_bytes_and_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tool = root / "python"
            file = root / "module.py"
            tool.write_bytes(b"tool")
            file.write_bytes(b"first")
            dist = SimpleNamespace(metadata={"Name": "fixture"}, version="1.0",
                                   files=[Path("module.py")], locate_file=lambda p: root / p)
            first = installed_identity((tool,), distributions=[dist], byte_limit=32)
            self.assertIsNotNone(first)
            self.assertEqual(first, installed_identity((tool,), distributions=[dist], byte_limit=32))
            file.write_bytes(b"other")
            self.assertNotEqual(first, installed_identity((tool,), distributions=[dist], byte_limit=32))
            self.assertIsNone(installed_identity((tool,), distributions=[dist], byte_limit=4))

    def test_retry_requires_fresh_evidence(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "GITHUB_RUN_ATTEMPT": "2",
                                     "BILQIS_VERIFICATION_FULL": "0"}):
            self.assertTrue(full_requested())

    def test_group_writable_local_database_cannot_supply_findings(self):
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
                os.environ, {"GITHUB_ACTIONS": "false"}):
            path = Path(temporary) / "ledger.sqlite3"
            with VerificationLedger(path) as ledger:
                ledger.record("scanner", "subject", [])
            path.chmod(0o666)
            with VerificationLedger(path) as ledger:
                self.assertIsNone(ledger.lookup("scanner", "subject", validate=lambda x: isinstance(x, list)))


if __name__ == "__main__":
    unittest.main()
