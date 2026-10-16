"""Behavioral contract of the import/status boundary auditor."""
from pathlib import Path
import tempfile
import unittest

from scripts.check_semantic_boundaries import inspect_semantic_boundaries
from bilqis_mlx.verification.outcomes import LawCheckStatus


ROOT = Path(__file__).resolve().parents[1]


class SemanticBoundaryTests(unittest.TestCase):
    def test_real_semantic_packages_obey_ownership(self):
        self.assertEqual(inspect_semantic_boundaries(ROOT), ())

    def test_linter_catches_illegal_import_and_inline_status(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            for part in ("semantics", "verification", "source_adapters"):
                (project / "bilqis_mlx" / part).mkdir(parents=True)
            (project / "bilqis_mlx" / "semantics" / "bad.py").write_text(
                'from bilqis_mlx.verification.laws import LawCheck\n'
                'from ..verification.outcomes import LawCheckStatus\n'
                f'STATUS = "{LawCheckStatus.COUNTEREXAMPLE.value}"\n', encoding="utf-8")
            problems = inspect_semantic_boundaries(project)
            self.assertEqual(len(problems), 3)
            self.assertEqual(sum("IMPORT_BOUNDARY" in line for line in problems), 2)
            self.assertTrue(any("RAW_RESULT_STATUS" in line for line in problems))


if __name__ == "__main__":
    unittest.main()
