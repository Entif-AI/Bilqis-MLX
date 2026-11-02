"""Re-enter source-owned A01/A03/A06 authority before preparing model inputs."""
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection, load_pinned_atlas_snapshot
from bilqis_mlx.semantics.released_frame_schemas import (
    _load_pinned_released_frame_schemas, _source_pins,
)
from .atlas_training_contracts import _invalid


def rederive_training_authority(config, features, selection, feature_schema):
    if (type(selection) is not AtlasArtifactSelection
            or type(feature_schema) is not FeatureSchema
            or feature_schema.predecessor is not None):
        _invalid('UPSTREAM_SEMANTIC_AUTHORITY_MISMATCH')
    snapshot = load_pinned_atlas_snapshot(selection)
    if build_feature_manifest(snapshot, feature_schema) != features:
        _invalid('UPSTREAM_SEMANTIC_AUTHORITY_MISMATCH')
    families = tuple(entry['family'] for entry in _source_pins()
                     if entry['semantic_release'] == snapshot.release_sha256
                     and entry['atlas_bundle_id'] == snapshot.bundle_id
                     and entry['source_bundle_id'] == snapshot.source_bundle_id
                     and entry['schema_map_sha256'] == config.schema_map.digest)
    if len(families) != 1:
        _invalid('UPSTREAM_SEMANTIC_AUTHORITY_MISMATCH')
    manifest = _load_pinned_released_frame_schemas(families[0], selection).manifest
    if config.schema_map != manifest.schema_map:
        _invalid('UPSTREAM_SEMANTIC_AUTHORITY_MISMATCH')
    canonical = {(body.schema_id, body.revision): body.parse() for body in manifest.bodies}
    if any(canonical.get((schema.schema_id, schema.revision)) != schema for schema in config.schemas):
        _invalid('UPSTREAM_SEMANTIC_AUTHORITY_MISMATCH')
