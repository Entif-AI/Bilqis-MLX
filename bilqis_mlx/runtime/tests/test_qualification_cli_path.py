"""Regression proof for the relocated qualification CLI owner."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


class QualificationCliPathTests(unittest.TestCase):
    def test_main_passes_repository_root_after_owner_relocation(self):
        from bilqis_mlx.runtime import qualification

        with TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "manifest.json"
            manifest.write_text("{}")
            observed = {}

            def execute(*args, **kwargs):
                observed["root"] = kwargs["root"]
                return {"status": "NOT_READY"}

            with patch.object(qualification, "execute", side_effect=execute):
                self.assertEqual(
                    qualification.main([
                        "--manifest", str(manifest),
                        "--arm", "fixture",
                        "--expected-digest", "a" * 64,
                        "--dry-run",
                    ]),
                    0,
                )

        expected = Path(qualification.__file__).resolve().parents[3]
        self.assertEqual(observed["root"], expected)
        self.assertTrue((observed["root"] / "bilqis_mlx").is_dir())


if __name__ == "__main__":
    unittest.main()
