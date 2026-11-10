"""Shared B13.5 accepted-generation feature authority test support."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.runtime.bamf_bundle import (
    issue_initial_foundation_feature_authority,
    publish_initial_generation,
    read_accepted_generation_feature_receipt,
)
from bilqis_mlx.runtime.bamf_bundle import feature_authority
from bilqis_mlx.runtime.bamf_bundle.genesis import foundation as genesis_foundation
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    genesis_preparation, publish_candidate, shape_patch,
)
from bilqis_mlx.runtime.tests.operator.test_admission import _executable_fixture
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_features import AtlasFeatures, FeatureSchema
from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot
from bilqis_mlx.semantics.atlas_projection_parts.releases import AtlasCounts


RELEASE = _executable_fixture()[0].release_sha256
ATLAS_RELEASE = "1" * 64
ATLAS_BUNDLE = "2" * 64
SOURCE_BUNDLE = "3" * 64
ARBITRARY = "b" * 64


def feature_schema() -> dict:
    """One recorded feature schema shape with no categorical bindings."""
    return {"role_ids": [], "schema_ids": [], "source_bindings": []}


def source_features(*, release=RELEASE) -> AtlasFeatures:
    return AtlasFeatures(
        release, ATLAS_BUNDLE, SOURCE_BUNDLE, None, (), (), (), (), ())


def feature_bound(source, features: AtlasFeatures, *, digest=None, release=RELEASE,
                  atlas_bundle=ATLAS_BUNDLE, source_bundle=SOURCE_BUNDLE,
                  active_set=None):
    """Bind a candidate to a recorded source release and feature map."""
    factor_map = digest or features.digest
    active_set = active_set or source.extents.active_semantic_digest
    return replace(
        source,
        extents=replace(
            source.extents, active_semantic_digest=active_set,
            factor_map_digest=factor_map),
        provenance=replace(source.provenance, release_digest=release),
        semantic_abi={**source.semantic_abi, "active_set_sha256": active_set},
        compiler_features={
            **source.compiler_features,
            "factor_map_sha256": factor_map,
            "feature_source": {
                "atlas_bundle_id": atlas_bundle,
                "release_sha256": release,
                "source_bundle_id": source_bundle},
            "feature_schema": feature_schema()},
        correction_frontier={
            **source.correction_frontier, "release_digest": release})


def frozen_snapshot(selection):
    return FrozenAtlasSnapshot(
        "bilqis.atlas.snapshot/v1", selection.bundle_id,
        selection.release_sha256, selection.source_bundle_id,
        "4" * 64, "5" * 64, "6" * 64, "7" * 64, "8" * 64, "9" * 64,
        "a" * 64, AtlasCounts(0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        (), (), (), (), (), (), (),
    )


class FeatureAuthorityTestBase(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.pointer = self.run / "bamf-state.json"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def publish(self, source):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_candidate(self.run, source)

    def source_replay(self, features):
        """Stand in for the externally supplied admitted source artifact."""
        return patch.multiple(
            feature_authority,
            resolve_atlas_artifact_selection=lambda identity: AtlasArtifactSelection(
                "/artifact", identity.bundle_id, identity.release_sha256,
                identity.source_bundle_id),
            load_pinned_atlas_snapshot=frozen_snapshot,
            build_feature_manifest=lambda snapshot, schema: features,
        )

    def foundation_replay(self, features):
        schema = FeatureSchema((), (), source_bindings=())
        return patch.multiple(
            genesis_foundation,
            _source_owned_feature_schema=lambda selection: (
                frozen_snapshot(selection), schema),
            build_feature_manifest=lambda snapshot, feature_schema: features,
        )

    def foundation_authority(self, features):
        selection = AtlasArtifactSelection(
            "/artifact", ATLAS_BUNDLE, features.semantic_release, SOURCE_BUNDLE)
        with self.foundation_replay(features):
            return issue_initial_foundation_feature_authority(selection)

    def publish_feature_genesis(self, features):
        authority = self.foundation_authority(features)
        with shape_patch(), self.foundation_replay(features), \
                patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_initial_generation(
                self.run, genesis_preparation(foundation_features=authority),
                reserve_gib=0.)

    def read_receipt(self, features):
        """Read the live accepted receipt under the custody and source seams."""
        with shape_patch(), self.source_replay(features):
            return read_accepted_generation_feature_receipt(self.pointer)
