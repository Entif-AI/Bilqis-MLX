"""The ABI guard must still detect new prohibited literals on a warm cache."""
from contextlib import redirect_stderr
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.check_historical_abi import detect_literal_prefix_count


class AbiVerificationReuseTests(unittest.TestCase):
    def test_warm_inventory_matches_full_and_changed_bytes_invalidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "bilqis_mlx"
            package.mkdir()
            source = package / "subject.py"
            source.write_text("value = 221\n", encoding="utf-8")
            with patch.dict(os.environ, {
                "GITHUB_ACTIONS": "false",
                "BILQIS_VERIFICATION_LEDGER": str(root / "ledger.sqlite3"),
                "BILQIS_VERIFICATION_FULL": "0",
            }):
                self.assertEqual(detect_literal_prefix_count(root, 222), ())
                log = io.StringIO()
                with redirect_stderr(log):
                    self.assertEqual(detect_literal_prefix_count(root, 222), ())
                self.assertIn("hits=1 misses=0", log.getvalue())
                stat = source.stat()
                source.write_text("value = 222\n", encoding="utf-8")
                os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
                expected = ("bilqis_mlx/subject.py:1",)
                self.assertEqual(detect_literal_prefix_count(root, 222), expected)
                self.assertEqual(detect_literal_prefix_count(root, 222, full=True), expected)
                self.assertEqual(detect_literal_prefix_count(root, 221), ())


if __name__ == "__main__":
    unittest.main()
