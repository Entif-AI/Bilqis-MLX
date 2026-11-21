"""Shared validation for owner-issued feature contexts."""
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_features import FeatureSchema
from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot

from ..records import invalid


def validate_materialized_feature_context(selection, snapshot, schema, features) -> None:
    if (type(selection) is not AtlasArtifactSelection
            or type(snapshot) is not FrozenAtlasSnapshot
            or type(schema) is not FeatureSchema
            or features.semantic_release != selection.release_sha256
            or features.atlas_bundle_id != selection.bundle_id
            or features.source_bundle_id != selection.source_bundle_id
            or snapshot.release_sha256 != selection.release_sha256
            or snapshot.bundle_id != selection.bundle_id
            or snapshot.source_bundle_id != selection.source_bundle_id):
        invalid("BAMF_FEATURE_CONTEXT_INVALID")
