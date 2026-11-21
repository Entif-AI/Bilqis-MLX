"""Clean-clone BAMF bootstrap assets remain complete and production-readable."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.bamf.build_bootstrap_assets import check as bootstrap_seed_is_current
from bilqis_mlx.bootstrap_assets import (
    ATLAS_BUNDLE_ID,
    ATLAS_MANIFEST,
    ATLAS_RELEASE_SHA256,
    ATLAS_ROOT,
    ATLAS_SOURCE_BUNDLE_ID,
    SOURCE_RUN,
)
from bilqis_mlx.presentation.operator_cli.bamf_lifecycle_inputs import (
    atlas_manifest_identity,
    fresh_source_run_dir,
    source_foundation,
    source_run_dir,
)
from bilqis_mlx.runtime.bamf_bundle import issue_initial_factory_foundation_authority
from bilqis_mlx.semantics.atlas.snapshot import (
    load_pinned_atlas_snapshot,
    resolve_atlas_artifact_selection,
)


class PackagedBootstrapAssetTests(unittest.TestCase):
    def test_packaged_source_seed_matches_current_factory_builder(self):
        self.assertTrue(bootstrap_seed_is_current())

    def test_default_source_seed_replays_current_factory_authority(self):
        self.assertEqual(fresh_source_run_dir(), SOURCE_RUN.resolve())
        source, release, graph = source_foundation(SOURCE_RUN)
        authority = issue_initial_factory_foundation_authority(source, graph)

        self.assertEqual(source, SOURCE_RUN.resolve())
        self.assertEqual(release, authority.release)
        self.assertEqual(
            release.foundation_capability_ids,
            release.execution_plan.active_capability_inventory,
        )
        self.assertEqual(
            tuple(grade.grade_id for grade in release.curriculum.grades),
            ("A", "B", "C"),
        )
        self.assertEqual(authority.origin_checkpoint.optimizer_step, 134808)

    def test_explicit_source_run_still_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(fresh_source_run_dir(tmp), Path(tmp).resolve())

    def test_existing_source_default_is_unchanged_outside_fresh_create(self):
        configured = Path("/configured/existing-source")
        with patch(
                "bilqis_mlx.presentation.operator_cli.bamf_lifecycle_inputs.active_run_dir",
                return_value=configured,
        ):
            self.assertEqual(source_run_dir(), configured)

    def test_packaged_atlas_manifest_and_artifact_validate_end_to_end(self):
        identity = atlas_manifest_identity(ATLAS_MANIFEST)
        self.assertEqual(
            (identity.bundle_id, identity.release_sha256, identity.source_bundle_id),
            (ATLAS_BUNDLE_ID, ATLAS_RELEASE_SHA256, ATLAS_SOURCE_BUNDLE_ID),
        )
        with patch.dict(os.environ, {
            "BILQIS_ATLAS_ARTIFACT_ROOT": "",
            "BILQIS_A01_ATLAS_BUNDLE": "",
            "BILQIS_ATLAS_REAL_ARTIFACT": "",
        }):
            selection = resolve_atlas_artifact_selection(identity)
        self.assertEqual(Path(selection.path), ATLAS_ROOT / ATLAS_BUNDLE_ID)
        snapshot = load_pinned_atlas_snapshot(selection)
        self.assertEqual(snapshot.bundle_id, ATLAS_BUNDLE_ID)
        self.assertEqual(snapshot.release_sha256, ATLAS_RELEASE_SHA256)
        self.assertEqual(snapshot.source_bundle_id, ATLAS_SOURCE_BUNDLE_ID)

    def test_explicit_atlas_root_still_wins(self):
        identity = atlas_manifest_identity(ATLAS_MANIFEST)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
                os.environ,
                {"BILQIS_ATLAS_ARTIFACT_ROOT": tmp},
        ):
            selection = resolve_atlas_artifact_selection(identity)
        self.assertEqual(Path(selection.path), Path(tmp) / ATLAS_BUNDLE_ID)


if __name__ == "__main__":
    unittest.main()
