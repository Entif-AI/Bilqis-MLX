"""Source-owned A06 feature selection over pinned A01/A03 authority."""
from __future__ import annotations

from .snapshot import AtlasArtifactSelection, load_pinned_atlas_snapshot
from .feature_io_contracts import _invalid
from .feature_io_storage import load_feature_manifest
from ..atlas_features import FeatureSchema, build_feature_manifest
from ..frame_adapters import (
    BOOLEAN_CONNECTIVE_ADAPTER,
    FINITE_NUMERIC_ADAPTER,
    MICRO_PREDICATE_ADAPTER,
    released_frame_adapter_ids,
)
from ..released_frame_schemas import _load_pinned_released_frame_schemas


# A06 feature geometry is selected by the source-frame surface the BAMF runtime
# actually admits, not by every A03 family that happens to exist in the repo.
# This keeps unrelated future schema families from silently changing established
# feature coordinates. A newly supported family must be deliberately added here
# together with its released source adapter.
_SOURCE_FAMILY_ADAPTERS = (
    ("boolean", BOOLEAN_CONNECTIVE_ADAPTER),
    ("micro", MICRO_PREDICATE_ADAPTER),
    ("numeric", FINITE_NUMERIC_ADAPTER),
)


def _source_owned_feature_schema(
    atlas_selection: AtlasArtifactSelection,
):
    """Rebuild the canonical A06 schema from source-owned released adapters."""
    if type(atlas_selection) is not AtlasArtifactSelection:
        _invalid("BAMF_FEATURE_SOURCE_SELECTION_INVALID")
    snapshot = load_pinned_atlas_snapshot(atlas_selection)
    released = set(released_frame_adapter_ids())
    required = {adapter for _family, adapter in _SOURCE_FAMILY_ADAPTERS}
    if not required <= released:
        _invalid("BAMF_FEATURE_SOURCE_ADAPTER_NOT_RELEASED")

    roles: set[str] = set()
    schemas: list[str] = []
    bindings: list[tuple[str, str]] = []
    for family, adapter in _SOURCE_FAMILY_ADAPTERS:
        manifest = _load_pinned_released_frame_schemas(
            family, atlas_selection).manifest
        for body in manifest.bodies:
            schema = body.parse()
            schemas.append(schema.schema_id)
            bindings.append((schema.schema_id, adapter))
            roles.update(role.role_id for role in schema.roles)

    try:
        feature_schema = FeatureSchema(
            tuple(sorted(roles)),
            tuple(sorted(schemas)),
            source_bindings=tuple(sorted(bindings)),
        )
    except Exception:
        _invalid("BAMF_FEATURE_SOURCE_PROFILE_INVALID")
    return snapshot, feature_schema


def load_source_pinned_feature_manifest(
    bundle_dir,
    *,
    atlas_selection: AtlasArtifactSelection,
):
    """Load the exact feature artifact implied by source-owned runtime support.

    The caller supplies only a locator. A01 selects the frozen Atlas release,
    released frame adapters select the A03 families, and A06 deterministically
    rebuilds the expected feature manifest. The loaded content-addressed artifact
    must match that source-derived identity exactly.

    This deliberately does not digest the global A03 registry. Adding an unrelated
    source family therefore cannot rewrite existing BAMF feature coordinates.
    """
    snapshot, feature_schema = _source_owned_feature_schema(atlas_selection)
    expected = build_feature_manifest(snapshot, feature_schema)
    features = load_feature_manifest(
        bundle_dir,
        expected_feature_digest=expected.digest,
        expected_semantic_release=snapshot.release_sha256,
        expected_source_bundle_id=snapshot.source_bundle_id,
        expected_atlas_bundle_id=snapshot.bundle_id,
        predecessor=None,
    )
    if features != expected:
        _invalid("BAMF_FEATURE_SOURCE_PROFILE_MISMATCH")
    return features
