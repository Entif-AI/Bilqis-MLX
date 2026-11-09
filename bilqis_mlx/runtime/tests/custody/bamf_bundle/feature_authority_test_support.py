"""Small source/feature fixtures shared by B13 feature-authority regressions."""
from dataclasses import replace

from bilqis_mlx.semantics.atlas_features import AtlasFeatures
from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot
from bilqis_mlx.semantics.atlas_projection_parts.releases import AtlasCounts

RELEASE = "1" * 64
ATLAS_BUNDLE = "2" * 64
SOURCE_BUNDLE = "3" * 64
SUCCESSOR_RELEASE = "c" * 64
SUCCESSOR_ATLAS_BUNDLE = "d" * 64
SUCCESSOR_SOURCE_BUNDLE = "e" * 64
ARBITRARY = "b" * 64


def feature_schema() -> dict:
    return {"role_ids": [], "schema_ids": [], "source_bindings": []}


def source_features() -> AtlasFeatures:
    return AtlasFeatures(
        RELEASE, ATLAS_BUNDLE, SOURCE_BUNDLE, None, (), (), (), (), ())


def feature_bound(source, features: AtlasFeatures, *, digest=None, release=RELEASE,
                  atlas_bundle=ATLAS_BUNDLE, source_bundle=SOURCE_BUNDLE):
    factor_map = digest or features.digest
    return replace(
        source,
        extents=replace(source.extents, factor_map_digest=factor_map),
        provenance=replace(source.provenance, release_digest=release),
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


def source_snapshot(selection):
    snapshot = frozen_snapshot(selection)
    if selection.release_sha256 != SUCCESSOR_RELEASE:
        return snapshot
    return replace(snapshot, prior_abi_sha256=ATLAS_BUNDLE)
