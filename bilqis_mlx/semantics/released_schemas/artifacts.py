"""Released frame-schema artifacts."""
from __future__ import annotations

from pathlib import Path
from ..atlas_projection import FrozenAtlasSnapshot
from ..frame_codec import SchemaTagMap
from ..frame_schema import FrameSchema
from .common import _fail
from .records import ReleasedFrameSchemaManifest, ReleasedSchemaBody


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
        _fail("FRAME_RELEASED_MANIFEST_SOURCE_INVALID")
    bodies = tuple(sorted(
        (ReleasedSchemaBody.from_schema(schema) for schema in schemas),
        key=lambda body: (body.schema_id.encode("utf-8"), body.revision)))
    return ReleasedFrameSchemaManifest(
        snapshot.release_sha256, snapshot.bundle_id,
        snapshot.source_bundle_id, schema_map, bodies)



def persist_released_frame_schemas(
    directory: Path, manifest: ReleasedFrameSchemaManifest,
) -> Path:
    """Append-only content-addressed source artifact, never overwrite a release."""
    if not isinstance(directory, Path) or not isinstance(
            manifest, ReleasedFrameSchemaManifest):
        _fail("FRAME_RELEASED_MANIFEST_PERSIST_INVALID")
    payload = manifest.canonical_bytes()
    path = directory / ("frame-schemas-" + manifest.digest + ".json")
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError:
        if path.read_bytes() != payload:
            _fail("FRAME_RELEASED_MANIFEST_EXISTING_DRIFT")
    return path
