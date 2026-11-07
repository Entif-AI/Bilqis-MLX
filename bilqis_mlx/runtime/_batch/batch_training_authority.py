"""Re-enter source-owned A01/A03/A06 authority before preparing model inputs."""
from bilqis_mlx.semantics.atlas.feature_io import load_source_pinned_feature_manifest
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection, load_pinned_atlas_snapshot
from bilqis_mlx.semantics.released_frame_schemas import (
    _load_pinned_released_frame_schemas, _source_pins,
)
from .atlas_training_contracts import _invalid


def rederive_training_authority(config, selection, feature_artifact_path):
    if type(selection) is not AtlasArtifactSelection:
        _invalid('UPSTREAM_SEMANTIC_AUTHORITY_MISMATCH')
    snapshot = load_pinned_atlas_snapshot(selection)
    if not config.schemas and not config.schema_map.entries:
        if config.schema_map.semantic_release != snapshot.release_sha256:
            _invalid('UPSTREAM_SEMANTIC_AUTHORITY_MISMATCH')
        return load_source_pinned_feature_manifest(
            feature_artifact_path, atlas_selection=selection)
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
    features = load_source_pinned_feature_manifest(
        feature_artifact_path, atlas_selection=selection)
    schemas, roles = dict(features.schema_map), dict(features.role_map)
    if (any(schema.schema_id not in schemas for schema in config.schemas)
            or any(role.role_id not in roles
                   for schema in config.schemas for role in schema.roles)):
        _invalid('UPSTREAM_SEMANTIC_AUTHORITY_MISMATCH')
    return features
