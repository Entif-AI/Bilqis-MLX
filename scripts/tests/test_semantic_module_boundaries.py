"""Behavioral contract of the import/status boundary auditor."""
import importlib
from pathlib import Path
import tempfile
import unittest

from scripts.check_semantic_boundaries import (
    SEMANTIC_IMPORT_ROLES,
    inspect_semantic_boundaries,
)
from bilqis_mlx.verification.outcomes import LawCheckStatus


ROOT = Path(__file__).resolve().parents[2]


class SemanticBoundaryTests(unittest.TestCase):
    def test_live_code_cannot_silently_activate_shadow_policy(self):
        for text in (
            "from .diagnostics.health_shadow import replay_health_shadow\n",
            "from bilqis_mlx.diagnostics import candidate_shadow\n",
            "import bilqis_mlx.diagnostics.candidate_shadow\n",
        ):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as temp:
                project = Path(temp)
                for part in ("semantics", "verification", "source_adapters"):
                    (project / "bilqis_mlx" / part).mkdir(parents=True)
                (project / "bilqis_mlx" / "trainer.py").write_text(text)
                problems = inspect_semantic_boundaries(project)
                self.assertTrue(any("UNAPPROVED_SHADOW_POLICY_IMPORT" in item for item in problems))

    def test_real_semantic_packages_obey_ownership(self):
        self.assertEqual(inspect_semantic_boundaries(ROOT), ())

    def test_legacy_atlas_alias_is_not_a_current_import_surface(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            for part in ("semantics", "verification", "source_adapters"):
                (project / "bilqis_mlx" / part).mkdir(parents=True)
            (project / "bilqis_mlx" / "consumer.py").write_text(
                "from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection\n"
                "from bilqis_mlx.semantics import atlas_snapshot\n",
                encoding="utf-8")
            (project / "bilqis_mlx" / "semantics" / "consumer.py").write_text(
                "from . import atlas_snapshot\n",
                encoding="utf-8")
            problems = inspect_semantic_boundaries(project)
            legacy = [
                item for item in problems
                if "SEMANTIC_IMPORT_ROLE LEGACY_COMPATIBILITY_ALIAS" in item
            ]
            self.assertEqual(len(legacy), 3)
            self.assertTrue(any("consumer.py:1" in item for item in legacy))
            self.assertTrue(any("consumer.py:2" in item for item in legacy))
            self.assertTrue(any("semantics/consumer.py:1" in item for item in legacy))

    def test_canonical_owner_and_declared_compatibility_facade_are_allowed(self):
        self.assertEqual(
            dict(SEMANTIC_IMPORT_ROLES)["bilqis_mlx.semantics.atlas.snapshot"],
            "CURRENT_SOURCE_OWNER")
        self.assertEqual(
            dict(SEMANTIC_IMPORT_ROLES)["bilqis_mlx.semantics.atlas_projection"],
            "HISTORICAL_COMPATIBILITY_FACADE")
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            for part in ("semantics", "verification", "source_adapters"):
                (project / "bilqis_mlx" / part).mkdir(parents=True)
            (project / "bilqis_mlx" / "consumer.py").write_text(
                "from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection\n"
                "from bilqis_mlx.semantics.atlas_projection import compile_atlas_release\n",
                encoding="utf-8")
            self.assertEqual(inspect_semantic_boundaries(project), ())

    def test_legacy_atlas_alias_remains_decode_only_compatible(self):
        canonical = importlib.import_module("bilqis_mlx.semantics.atlas.snapshot")
        legacy = importlib.import_module("bilqis_mlx.semantics.atlas_snapshot")
        self.assertIs(legacy, canonical)

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
