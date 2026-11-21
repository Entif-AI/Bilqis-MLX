"""Human BAMF resume migrates only the exact pre-checkpoint accepted state."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.presentation.operator_cli.bamf_resume_migration import (
    _load_resume_generation_authority,
)
from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
    _reset_execution_cache_owner_for_tests,
)
from bilqis_mlx.runtime.bamf_bundle.publication.accepted_authority_checkpoint import (
    read_protected_accepted_authority_tip,
)
import bilqis_mlx.runtime.bamf_bundle.publication as publication
from bilqis_mlx.runtime.tests.custody.bamf_bundle.genesis_authority_fixtures import (
    accepted_feature_source_patch,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, parent_state, publish_candidate, publish_genesis, shape_patch,
)


class AcceptedAuthorityResumeMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        _reset_execution_cache_owner_for_tests()
        self.environment.stop()
        self.temporary.cleanup()

    def _publish_legacy_accepted_run(self):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), patch.object(
                publication, "commit_accepted_authority", create=True):
            with patch(
                    "bilqis_mlx.runtime.bamf_bundle.publication.accepted_authority_commit."
                    "commit_accepted_authority"):
                publish_candidate(self.run, candidate(parent_state()))
        self.assertIsNone(read_protected_accepted_authority_tip("fixture-run"))

    def test_human_resume_backfills_legacy_checkpoint_then_loads_current_generation(self):
        self._publish_legacy_accepted_run()
        args = SimpleNamespace(human_run=True, dry_run=False)

        with shape_patch(), accepted_feature_source_patch():
            student, manifest_sha256 = _load_resume_generation_authority(
                args, self.run, self.run / "bamf-state.json")

        checkpoint = read_protected_accepted_authority_tip("fixture-run")
        self.assertIsNotNone(checkpoint)
        self.assertEqual(checkpoint.kind, "AUDIT_BACKFILL")
        self.assertEqual(checkpoint.manifest_sha256, manifest_sha256)
        self.assertEqual(student.generation, 0)

    def test_dry_run_keeps_missing_checkpoint_fail_closed_and_non_mutating(self):
        self._publish_legacy_accepted_run()
        args = SimpleNamespace(human_run=True, dry_run=True)

        with shape_patch(), accepted_feature_source_patch(), self.assertRaises(
                BilqisError) as raised:
            _load_resume_generation_authority(
                args, self.run, self.run / "bamf-state.json")

        self.assertEqual(
            raised.exception.context["reason"],
            "BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_REQUIRED",
        )
        self.assertIsNone(read_protected_accepted_authority_tip("fixture-run"))

    def test_current_checkpoint_load_does_not_enter_legacy_migration(self):
        with shape_patch():
            publish_genesis(self.run)
        args = SimpleNamespace(human_run=True, dry_run=False)

        with shape_patch():
            student, manifest_sha256 = _load_resume_generation_authority(
                args, self.run, self.run / "bamf-state.json")

        checkpoint = read_protected_accepted_authority_tip("fixture-run")
        self.assertIsNotNone(checkpoint)
        self.assertEqual(checkpoint.kind, "GENESIS")
        self.assertEqual(checkpoint.manifest_sha256, manifest_sha256)
        self.assertEqual(student.generation, 0)
        self.assertFalse((self.run / "bamf-authority-migrations").exists())


if __name__ == "__main__":
    unittest.main()
