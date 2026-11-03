"""Released frame-schema io with source-owned authority."""
from __future__ import annotations
from .. import released_frame_schemas as _facade
from pathlib import Path
from ...errors import BilqisError
from ..atlas_projection import FrozenAtlasSnapshot
from ..frame_codec import SchemaTagEntry, SchemaTagMap
from ..frame_schema import FrameSchema
from .contracts import _SHA
from .models import (
    ReleasedSchemaBody, ReleasedFrameSchemaManifest, VerifiedReleasedFrameSchemas,
)


def seal_released_frame_schemas(
    schemas: tuple[FrameSchema, ...],
    schema_map: SchemaTagMap,
    snapshot: FrozenAtlasSnapshot,
) -> ReleasedFrameSchemaManifest:
    """Source-owner issuance step; staging alone confers no trust to consumers."""
    if (not isinstance(snapshot, FrozenAtlasSnapshot)
            or not isinstance(schemas, tuple)
            or any(not isinstance(schema, FrameSchema) for schema in schemas)
            or not isinstance(schema_map, SchemaTagMap)
            or schema_map.semantic_release != snapshot.release_sha256):
        _facade._fail("FRAME_RELEASED_MANIFEST_SOURCE_INVALID")
    bodies = tuple(sorted(
        (ReleasedSchemaBody.from_schema(schema) for schema in schemas),
        key=lambda body: (body.schema_id.encode("utf-8"), body.revision)))
    return ReleasedFrameSchemaManifest(
        snapshot.release_sha256, snapshot.bundle_id,
        snapshot.source_bundle_id, schema_map, bodies)



def load_released_frame_schemas(
    payload: bytes,
    *,
    expected_sha256: str,
    snapshot: FrozenAtlasSnapshot,
    expected_semantic_release: str | None = None,
    expected_schema_map_sha256: str | None = None,
) -> VerifiedReleasedFrameSchemas:
    """Consumer entrypoint: require a digest from the accepted A03 source release."""
    if (not isinstance(snapshot, FrozenAtlasSnapshot)
            or not isinstance(expected_sha256, str)
            or not _SHA.fullmatch(expected_sha256)
            or not isinstance(payload, bytes)
            or _facade._sha(payload) != expected_sha256):
        _facade._fail("FRAME_RELEASED_MANIFEST_DIGEST_MISMATCH")
    value = _facade._json(payload)
    if set(value) != {
            "schema_version", "semantic_release", "atlas_bundle_id",
            "source_bundle_id", "schema_map", "bodies"}:
        _facade._fail("FRAME_RELEASED_MANIFEST_INVALID")
    try:
        tag_map = value["schema_map"]
        if set(tag_map) != {"semantic_release", "entries", "schema_version"}:
            _facade._fail("FRAME_RELEASED_MANIFEST_INVALID")
        manifest = ReleasedFrameSchemaManifest(
            semantic_release=value["semantic_release"],
            atlas_bundle_id=value["atlas_bundle_id"],
            source_bundle_id=value["source_bundle_id"],
            schema_map=SchemaTagMap(
                semantic_release=tag_map["semantic_release"],
                entries=tuple(SchemaTagEntry(**entry)
                              for entry in tag_map["entries"]),
                schema_version=tag_map["schema_version"]),
            bodies=tuple(ReleasedSchemaBody(**body)
                         for body in value["bodies"]),
            schema_version=value["schema_version"],
        )
    except BilqisError:
        raise
    except (KeyError, TypeError, ValueError):
        _facade._fail("FRAME_RELEASED_MANIFEST_INVALID")
    if payload != manifest.canonical_bytes():
        _facade._fail("FRAME_RELEASED_MANIFEST_NONCANONICAL")
    if (manifest.semantic_release != snapshot.release_sha256
            or manifest.atlas_bundle_id != snapshot.bundle_id
            or manifest.source_bundle_id != snapshot.source_bundle_id):
        _facade._fail("FRAME_RELEASED_MANIFEST_ATLAS_SOURCE_MISMATCH")
    if (expected_semantic_release is not None
            and manifest.semantic_release != expected_semantic_release):
        _facade._fail("FRAME_RELEASED_MANIFEST_RELEASE_MISMATCH")
    if (expected_schema_map_sha256 is not None
            and manifest.schema_map.digest != expected_schema_map_sha256):
        _facade._fail("FRAME_RELEASED_SCHEMA_MAP_MISMATCH")
    return VerifiedReleasedFrameSchemas(manifest, expected_sha256)



def persist_released_frame_schemas(
    directory: Path, manifest: ReleasedFrameSchemaManifest,
) -> Path:
    """Append-only content-addressed source artifact, never overwrite a release."""
    if not isinstance(directory, Path) or not isinstance(
            manifest, ReleasedFrameSchemaManifest):
        _facade._fail("FRAME_RELEASED_MANIFEST_PERSIST_INVALID")
    payload = manifest.canonical_bytes()
    path = directory / ("frame-schemas-" + manifest.digest + ".json")
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError:
        if path.read_bytes() != payload:
            _facade._fail("FRAME_RELEASED_MANIFEST_EXISTING_DRIFT")
    return path
