"""Stable path anchors for compartmentalized Ithkuil tests."""
from pathlib import Path
TEST_ROOT = Path(__file__).resolve().parent
ITHKUIL_ROOT = TEST_ROOT.parent
REPO_ROOT = ITHKUIL_ROOT.parents[1]
FIXTURES = TEST_ROOT / "fixtures"
