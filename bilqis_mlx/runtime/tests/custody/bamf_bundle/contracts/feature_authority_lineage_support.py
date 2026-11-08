"""Shared fixtures for B13.5 accepted feature-lineage contract tests."""
from __future__ import annotations

import os
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.runtime.bamf_bundle import (
    feature_authority, issue_initial_foundation_feature_authority,
    publish_initial_generation,
)
from bilqis_mlx.runtime.bamf_bundle import genesis_foundation
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_features import FeatureSchema
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.test_feature_authority import (
    frozen_snapshot,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    genesis_preparation, publish_candidate, shape_patch,
)

SUCCESSOR_RELEASE = "c" * 64
SUCCESSOR_ATLAS_BUNDLE = "d" * 64
SUCCESSOR_SOURCE_BUNDLE = "e" * 64


def publish_feature_genesis(
        run_dir, features, *, selection=None, snapshot=None, schema=None):
    """Publish custom Atlas foundation through the production bootstrap owner."""
    selection = selection or AtlasArtifactSelection(
        "/artifact", features.atlas_bundle_id, features.semantic_release,
        features.source_bundle_id)
    snapshot = snapshot or frozen_snapshot(selection)
    schema = schema or FeatureSchema((), (), source_bindings=())
    # Custody tests deliberately use a two-row identity bank. Preserve the real
    # source/release/active-set/feature identities while projecting only rows
    # representable by that tiny numerical fixture into FOUNDATION plasticity.
    bootstrap_snapshot = replace(
        snapshot,
        abi_entries=tuple(
            replace(entry, active=(entry.active and entry.bank == 0 and entry.row < 2))
            for entry in snapshot.abi_entries))
    replay = patch.multiple(
        genesis_foundation,
        _source_owned_feature_schema=lambda selected: (bootstrap_snapshot, schema),
        build_feature_manifest=lambda selected_snapshot, selected_schema: features,
    )
    with shape_patch(), replay:
        authority = issue_initial_foundation_feature_authority(selection)
        prepared = genesis_preparation(foundation_features=authority)
        with patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_initial_generation(
                run_dir, prepared, reserve_gib=0.)


class FeatureLineageCase(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.pointer = self.run / "bamf-state.json"
        self.environment = patch.dict(
            os.environ, {
                "BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3"),
                "BILQIS_ATLAS_ARTIFACT_ROOT": str(self.root / "atlas"),
            })
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def publish(self, source):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_candidate(self.run, source)

    def publish_feature_genesis(self, features, **kwargs):
        return publish_feature_genesis(self.run, features, **kwargs)

    def source_replay(self, features):
        return patch.multiple(
            feature_authority,
            load_pinned_atlas_snapshot=frozen_snapshot,
            build_feature_manifest=lambda snapshot, schema: features,
        )
