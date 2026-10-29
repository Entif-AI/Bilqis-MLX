"""Tests for anti-laundering governance integrity checks."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).parents[1] / "quality/check_governance_integrity.py"
spec = importlib.util.spec_from_file_location("check_governance_integrity", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class GovernanceIntegrityTests(unittest.TestCase):
    def test_threshold_parser_requires_ratified_values(self):
        source = b"\n".join([
            b"FILE_TRIGGER = 360",
            b"FILE_TARGET = 240",
            b"DIRECTORY_TRIGGER = 18",
            b"DIRECTORY_TARGET = 12",
        ])
        self.assertEqual(check._thresholds(source), dict(check.EXPECTED))
        drifted = source.replace(b"FILE_TRIGGER = 360", b"FILE_TRIGGER = 500")
        self.assertNotEqual(check._thresholds(drifted), dict(check.EXPECTED))

    def test_smell_baseline_allows_path_move_without_new_debt(self):
        base = {"schema": "bilqis.code-smell-baseline/v1",
                "fingerprints": [["old.py", "long-function", "work"]]}
        moved = {"schema": "bilqis.code-smell-baseline/v1",
                 "fingerprints": [["new.py", "long-function", "work"]]}
        self.assertEqual(check.smell_baseline_problems(base, moved), [])

    def test_smell_baseline_rejects_new_grandfathered_finding(self):
        base = {"schema": "bilqis.code-smell-baseline/v1", "fingerprints": []}
        current = {"schema": "bilqis.code-smell-baseline/v1",
                   "fingerprints": [["x.py", "long-function", "work"]]}
        result = check.smell_baseline_problems(base, current)
        self.assertEqual(len(result), 1)
        self.assertIn("CODE_SMELL_BASELINE_EXPANSION", result[0])

    def test_size_baseline_may_shrink_but_not_grow(self):
        base = {"schema": "bilqis.production-size-baseline/v1", "sizes": {"x.py": 900}}
        reduced = {"schema": "bilqis.production-size-baseline/v1", "sizes": {"x.py": 700}}
        increased = {"schema": "bilqis.production-size-baseline/v1", "sizes": {"x.py": 901}}
        added = {"schema": "bilqis.production-size-baseline/v1",
                 "sizes": {"x.py": 900, "y.py": 500}}
        self.assertEqual(check.size_baseline_problems(base, reduced), [])
        self.assertTrue(check.size_baseline_problems(base, increased))
        self.assertTrue(check.size_baseline_problems(base, added))


if __name__ == "__main__":
    unittest.main()
