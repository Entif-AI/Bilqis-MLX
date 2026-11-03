"""Released frame-schema verification."""
from __future__ import annotations

from dataclasses import dataclass
from ...errors import BilqisError
from ..atlas_projection import FrozenAtlasSnapshot
from ..frame_codec import SchemaTagEntry, SchemaTagMap, _canonical_bytes
from ..frame_schema import FrameSchema, frame_schema_from_bytes
from .common import _SHA, _fail, _json, _sha
from .records import ReleasedFrameSchemaManifest, ReleasedSchemaBody, ReleasedSchemaBodyWitness


@dataclass(frozen=True)
class VerifiedReleasedFrameSchemas:
    """A manifest verified against a source-owner pinned release digest."""
    manifest: ReleasedFrameSchemaManifest
    trusted_sha256: str

    def __post_init__(self) -> None:
        if (not isinstance(self.manifest, ReleasedFrameSchemaManifest)
                or not isinstance(self.trusted_sha256, str)
                or not _SHA.fullmatch(self.trusted_sha256)
                or self.manifest.digest != self.trusted_sha256):
            _fail("FRAME_RELEASED_MANIFEST_DIGEST_MISMATCH")

    def canonical_bytes(self) -> bytes:
        return self.manifest.canonical_bytes()

    def lookup(self, schema_id: str, revision: int) -> ReleasedSchemaBodyWitness:
        body = next((
            item for item in self.manifest.bodies
            if (item.schema_id, item.revision) == (schema_id, revision)
        ), None)
        if body is None:
            _fail("FRAME_RELEASED_SCHEMA_UNKNOWN")
        return ReleasedSchemaBodyWitness(
            self.manifest.semantic_release,
            body.schema_id, body.revision, body.schema_body_sha256,
            self.manifest.schema_map.digest, self.trusted_sha256)

    def require_schema(
        self, schema: FrameSchema, witness: ReleasedSchemaBodyWitness,
    ) -> FrameSchema:
        if (not isinstance(schema, FrameSchema)
                or not isinstance(witness, ReleasedSchemaBodyWitness)
                or witness != self.lookup(
                    schema.schema_id, schema.revision)):
            _fail("FRAME_RELEASED_SCHEMA_WITNESS_MISMATCH")
        if _sha(schema.canonical_bytes()) != witness.schema_body_sha256:
            _fail("FRAME_RELEASED_SCHEMA_BODY_MISMATCH")
        return schema

    def require_schema_bytes(
        self, payload: bytes, witness: ReleasedSchemaBodyWitness,
    ) -> FrameSchema:
        # JSON object key order is not semantic. Role-array order *is*.
        schema = frame_schema_from_bytes(_canonical_bytes(_json(payload)))
        return self.require_schema(schema, witness)



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
            or _sha(payload) != expected_sha256):
        _fail("FRAME_RELEASED_MANIFEST_DIGEST_MISMATCH")
    value = _json(payload)
    if set(value) != {
            "schema_version", "semantic_release", "atlas_bundle_id",
            "source_bundle_id", "schema_map", "bodies"}:
        _fail("FRAME_RELEASED_MANIFEST_INVALID")
    try:
        tag_map = value["schema_map"]
        if set(tag_map) != {"semantic_release", "entries", "schema_version"}:
            _fail("FRAME_RELEASED_MANIFEST_INVALID")
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
        _fail("FRAME_RELEASED_MANIFEST_INVALID")
    if payload != manifest.canonical_bytes():
        _fail("FRAME_RELEASED_MANIFEST_NONCANONICAL")
    if (manifest.semantic_release != snapshot.release_sha256
            or manifest.atlas_bundle_id != snapshot.bundle_id
            or manifest.source_bundle_id != snapshot.source_bundle_id):
        _fail("FRAME_RELEASED_MANIFEST_ATLAS_SOURCE_MISMATCH")
    if (expected_semantic_release is not None
            and manifest.semantic_release != expected_semantic_release):
        _fail("FRAME_RELEASED_MANIFEST_RELEASE_MISMATCH")
    if (expected_schema_map_sha256 is not None
            and manifest.schema_map.digest != expected_schema_map_sha256):
        _fail("FRAME_RELEASED_SCHEMA_MAP_MISMATCH")
    return VerifiedReleasedFrameSchemas(manifest, expected_sha256)

