"""Released frame-schema models with source-owned authority."""
from __future__ import annotations
from .._public_identity.facade_dependency import public_facade as _public_facade

def _public():
    return _public_facade("bilqis_mlx.semantics.released_frame_schemas")
from dataclasses import asdict, dataclass
from ..frame_codec import SchemaTagMap, _canonical_bytes
from ..frame_schema import FrameSchema, frame_schema_from_bytes
from .contracts import (
    _fail, _sha, _json, MANIFEST_SCHEMA, BODY_SCHEMA, WITNESS_SCHEMA, _SHA,
)


@dataclass(frozen=True)
class ReleasedSchemaBody:
    schema_id: str
    revision: int
    schema_body_sha256: str
    canonical_body_json: str
    schema_version: str = BODY_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.schema_id, str) or not self.schema_id
                or type(self.revision) is not int or self.revision < 1
                or not isinstance(self.schema_body_sha256, str)
                or not _SHA.fullmatch(self.schema_body_sha256)
                or not isinstance(self.canonical_body_json, str)
                or self.schema_version != BODY_SCHEMA):
            _public()._fail("FRAME_RELEASED_SCHEMA_BODY_INVALID")
        body = self.canonical_body_json.encode("utf-8")
        schema = _public().frame_schema_from_bytes(body)
        if ((schema.schema_id, schema.revision)
                != (self.schema_id, self.revision)
                or _public()._sha(body) != self.schema_body_sha256):
            _public()._fail("FRAME_RELEASED_SCHEMA_BODY_INVALID")

    @classmethod
    def from_schema(cls, schema: FrameSchema) -> "ReleasedSchemaBody":
        if not isinstance(schema, FrameSchema):
            _public()._fail("FRAME_RELEASED_SCHEMA_BODY_INVALID")
        payload = schema.canonical_bytes()
        return cls(
            schema.schema_id, schema.revision, _public()._sha(payload),
            payload.decode("utf-8"))

    def parse(self) -> FrameSchema:
        return _public().frame_schema_from_bytes(self.canonical_body_json.encode("utf-8"))



@dataclass(frozen=True)
class ReleasedFrameSchemaManifest:
    semantic_release: str
    atlas_bundle_id: str
    source_bundle_id: str
    schema_map: SchemaTagMap
    bodies: tuple[ReleasedSchemaBody, ...]
    schema_version: str = MANIFEST_SCHEMA

    def __post_init__(self) -> None:
        if (not all(isinstance(item, str) and _SHA.fullmatch(item)
                    for item in (
                        self.semantic_release, self.atlas_bundle_id,
                        self.source_bundle_id))
                or not isinstance(self.schema_map, SchemaTagMap)
                or self.schema_map.semantic_release != self.semantic_release
                or not isinstance(self.bodies, tuple) or not self.bodies
                or any(not isinstance(body, ReleasedSchemaBody)
                       for body in self.bodies)
                or self.bodies != tuple(sorted(
                    self.bodies, key=lambda body: (
                        body.schema_id.encode("utf-8"), body.revision)))
                or self.schema_version != MANIFEST_SCHEMA):
            _public()._fail("FRAME_RELEASED_MANIFEST_INVALID")
        identities = tuple(
            (body.schema_id, body.revision) for body in self.bodies)
        if len(identities) != len(set(identities)):
            _public()._fail("FRAME_RELEASED_SCHEMA_DUPLICATE")
        if self.schema_map != SchemaTagMap.from_schemas(
                self.semantic_release,
                tuple(body.parse() for body in self.bodies)):
            _public()._fail("FRAME_RELEASED_SCHEMA_MAP_MISMATCH")

    def canonical_bytes(self) -> bytes:
        return _public()._canonical_bytes({
            "schema_version": self.schema_version,
            "semantic_release": self.semantic_release,
            "atlas_bundle_id": self.atlas_bundle_id,
            "source_bundle_id": self.source_bundle_id,
            "schema_map": _public().asdict(self.schema_map),
            "bodies": [_public().asdict(body) for body in self.bodies],
        })

    @property
    def digest(self) -> str:
        return _public()._sha(self.canonical_bytes())



@dataclass(frozen=True)
class ReleasedSchemaBodyWitness:
    semantic_release: str
    schema_id: str
    revision: int
    schema_body_sha256: str
    schema_map_sha256: str
    release_manifest_sha256: str
    schema_version: str = WITNESS_SCHEMA



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
            _public()._fail("FRAME_RELEASED_MANIFEST_DIGEST_MISMATCH")

    def canonical_bytes(self) -> bytes:
        return self.manifest.canonical_bytes()

    def lookup(self, schema_id: str, revision: int) -> ReleasedSchemaBodyWitness:
        body = next((
            item for item in self.manifest.bodies
            if (item.schema_id, item.revision) == (schema_id, revision)
        ), None)
        if body is None:
            _public()._fail("FRAME_RELEASED_SCHEMA_UNKNOWN")
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
            _public()._fail("FRAME_RELEASED_SCHEMA_WITNESS_MISMATCH")
        if _public()._sha(schema.canonical_bytes()) != witness.schema_body_sha256:
            _public()._fail("FRAME_RELEASED_SCHEMA_BODY_MISMATCH")
        return schema

    def require_schema_bytes(
        self, payload: bytes, witness: ReleasedSchemaBodyWitness,
    ) -> FrameSchema:
        # JSON object key order is not semantic. Role-array order *is*.
        schema = _public().frame_schema_from_bytes(_public()._canonical_bytes(_public()._json(payload)))
        return self.require_schema(schema, witness)
