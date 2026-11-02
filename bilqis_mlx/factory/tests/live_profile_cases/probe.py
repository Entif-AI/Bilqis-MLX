from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
from bilqis_mlx.factory.tests.live_profile_cases.source_setup import PROBE as _SOURCE_SETUP
from bilqis_mlx.factory.tests.live_profile_cases.boolean_profile import PROBE as _BOOLEAN_PROFILE
from bilqis_mlx.factory.tests.live_profile_cases.projection import PROBE as _PROJECTION
from bilqis_mlx.factory.tests.live_profile_cases.numeric_profile import PROBE as _NUMERIC_PROFILE

LIVE_PROFILE_PROBE = _SOURCE_SETUP + _BOOLEAN_PROFILE + _PROJECTION + _NUMERIC_PROFILE

def _run_live_profile_probe():
    return subprocess.run(
        [sys.executable, "-B", "-c", LIVE_PROFILE_PROBE], cwd=ROOT,
        capture_output=True, text=True, check=False)
