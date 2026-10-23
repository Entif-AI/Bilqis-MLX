"""The torch-free teacher projection must remain behavior-identical."""
from copy import deepcopy
import json
from pathlib import Path
import random
import sys
import unittest

from bilqis_mlx.compatibility import historical_teacher_policy as projected


ROOT = Path(__file__).resolve().parents[3]
LEGACY_ROOT = ROOT / "vendor" / "legacy-v16"
TEACHER_STATE = (
    LEGACY_ROOT / "runs" / "primitive-consolidation-v16-triplets" / "state.json"
)


@unittest.skipUnless(TEACHER_STATE.is_file(), "Historical teacher state not mounted")
class HistoricalTeacherPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if str(LEGACY_ROOT) not in sys.path:
            sys.path.insert(0, str(LEGACY_ROOT))
        from bilqis_school import engine
        cls.legacy = engine
        cls.teacher = json.loads(TEACHER_STATE.read_text())["teacher"]

    def test_pick_and_observe_match_legacy_policy(self):
        for seed in (1, 7, 52, 991):
            with self.subTest(seed=seed):
                left = deepcopy(self.teacher)
                right = deepcopy(self.teacher)
                legacy_rng = random.Random(seed)
                projected_rng = random.Random(seed)
                legacy_choice = self.legacy.pick(left, "A", legacy_rng)
                projected_choice = projected.pick(right, "A", projected_rng)
                self.assertEqual(projected_choice, legacy_choice)
                self.assertEqual(right, left)
                projected.observe(right, "A", projected_choice[0], 0.125)
                self.legacy.observe(left, "A", legacy_choice[0], 0.125)
                self.assertEqual(right, left)
