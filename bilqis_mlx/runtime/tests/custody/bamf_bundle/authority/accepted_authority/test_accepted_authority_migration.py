"""Issue #1526: legacy authority backfill is explicit, never a runtime fallback."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
    _reset_execution_cache_owner_for_tests,
)
from bilqis_mlx.runtime.bamf_bundle.publication.accepted_authority_migration import (
    backfill_current_accepted_authority,
)
from bilqis_mlx.runtime.bamf_bundle.publication.accepted_authority_checkpoint import (
    read_protected_accepted_authority_tip,
)
from bilqis_mlx.runtime.bamf_operator.locking import bamf_operator_lock
import bilqis_mlx.runtime.bamf_bundle.publication as publication
from bilqis_mlx.runtime.tests.custody.bamf_bundle.genesis_authority_fixtures import (
    accepted_feature_source_patch,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, parent_state, publish_candidate, shape_patch,
)


class AcceptedAuthorityMigrationTests(unittest.TestCase):
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

    def test_missing_checkpoint_requires_explicit_backfill(self):
        # Simulate a pre-#1526 owner publication: genesis trust exists, but no
        # accepted-authority checkpoint/tip was minted.
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), patch.object(
                publication, "commit_accepted_authority", create=True):
            # _publish_authorized_generation imports the helper lazily, so patch
            # the helper module rather than relying on a package attribute.
            with patch(
                    "bilqis_mlx.runtime.bamf_bundle.publication.accepted_authority_commit."
                    "commit_accepted_authority"):
                publish_candidate(self.run, candidate(parent_state()))

        _reset_execution_cache_owner_for_tests()
        with shape_patch(), self.assertRaises(BilqisError) as missing:
            load_accepted_generation(self.run)
        self.assertEqual(
            missing.exception.context["reason"],
            "BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_REQUIRED",
        )

        with bamf_operator_lock(self.run), shape_patch(), accepted_feature_source_patch():
            with self.assertRaises(BilqisError) as active:
                backfill_current_accepted_authority(self.run)
        self.assertEqual(
            active.exception.context["reason"],
            "BAMF_ACCEPTED_AUTHORITY_MIGRATION_OPERATOR_ACTIVE",
        )
        self.assertIsNone(read_protected_accepted_authority_tip("run"))

        with bamf_operator_lock(self.run) as custody, shape_patch(), accepted_feature_source_patch():
            checkpoint = backfill_current_accepted_authority(
                self.run, operator_custody=custody)
            self.assertEqual(checkpoint.kind, "AUDIT_BACKFILL")
            from bilqis_mlx.runtime.bamf_operator.locking import bamf_operator_lock_held
            self.assertIs(bamf_operator_lock_held(self.run), True)

        with shape_patch(), accepted_feature_source_patch(), self.assertRaises(
                BilqisError) as stale:
            backfill_current_accepted_authority(self.run, operator_custody=custody)
        self.assertEqual(
            stale.exception.context["reason"],
            "BAMF_ACCEPTED_AUTHORITY_MIGRATION_OPERATOR_CUSTODY_INVALID",
        )

        other = self.root / "other-run"
        with bamf_operator_lock(self.run) as custody, self.assertRaises(
                BilqisError) as wrong_run:
            backfill_current_accepted_authority(other, operator_custody=custody)
        self.assertEqual(
            wrong_run.exception.context["reason"],
            "BAMF_ACCEPTED_AUTHORITY_MIGRATION_OPERATOR_CUSTODY_INVALID",
        )

        with shape_patch(), accepted_feature_source_patch():
            repeated = backfill_current_accepted_authority(self.run)
        self.assertEqual(checkpoint.kind, "AUDIT_BACKFILL")
        self.assertEqual(checkpoint.generation, 0)
        self.assertEqual(repeated, checkpoint)

        _reset_execution_cache_owner_for_tests()
        with shape_patch():
            accepted = load_accepted_generation(self.run)
        self.assertEqual(accepted.generation, 0)


if __name__ == "__main__":
    unittest.main()
