from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT.parent / "bilqis-mlx-retention-lab" / "vendor" / "legacy-v16"


from bilqis_mlx.factory.tests.live_profile_cases.probe import _run_live_profile_probe


@unittest.skipUnless(SOURCE.is_dir(), "Pinned historic source not mounted")
class LiveProfileExecutionTests(unittest.TestCase):
    def test_real_full_b_provider_executes_and_iff_profile_without_minimal_provider(self):
        result = _run_live_profile_probe()
        self.assertEqual(
            result.returncode, 0,
            msg="stdout:\n" + result.stdout + "\nstderr:\n" + result.stderr)
        self.assertIn("LIVE_PROFILE_EXECUTION_OK", result.stdout)
