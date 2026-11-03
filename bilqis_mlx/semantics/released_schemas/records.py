"""Released frame-schema records."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from ..frame_codec import SchemaTagMap, _canonical_bytes
from ..frame_schema import FrameSchema, frame_schema_from_bytes
from .common import BODY_SCHEMA, MANIFEST_SCHEMA, WITNESS_SCHEMA, _SHA, _fail, _sha


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
            _fail("FRAME_RELEASED_SCHEMA_BODY_INVALID")
        body = self.canonical_body_json.encode("utf-8")
        schema = frame_schema_from_bytes(body)
        if ((schema.schema_id, schema.revision)
                != (self.schema_id, self.revision)
                or _sha(body) != self.schema_body_sha256):
            _fail("FRAME_RELEASED_SCHEMA_BODY_INVALID")

    @classmethod
    def from_schema(cls, schema: FrameSchema) -> "ReleasedSchemaBody":
        if not isinstance(schema, FrameSchema):
            _fail("FRAME_RELEASED_SCHEMA_BODY_INVALID")
        payload = schema.canonical_bytes()
        return cls(
            schema.schema_id, schema.revision, _sha(payload),
            payload.decode("utf-8"))

    def parse(self) -> FrameSchema:
        return frame_schema_from_bytes(self.canonical_body_json.encode("utf-8"))



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
            _fail("FRAME_RELEASED_MANIFEST_INVALID")
        identities = tuple(
            (body.schema_id, body.revision) for body in self.bodies)
        if len(identities) != len(set(identities)):
            _fail("FRAME_RELEASED_SCHEMA_DUPLICATE")
        if self.schema_map != SchemaTagMap.from_schemas(
                self.semantic_release,
                tuple(body.parse() for body in self.bodies)):
            _fail("FRAME_RELEASED_SCHEMA_MAP_MISMATCH")

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes({
            "schema_version": self.schema_version,
            "semantic_release": self.semantic_release,
            "atlas_bundle_id": self.atlas_bundle_id,
            "source_bundle_id": self.source_bundle_id,
            "schema_map": asdict(self.schema_map),
            "bodies": [asdict(body) for body in self.bodies],
        })

    @property
    def digest(self) -> str:
        return _sha(self.canonical_bytes())



@dataclass(frozen=True)
class ReleasedSchemaBodyWitness:
    semantic_release: str
    schema_id: str
    revision: int
    schema_body_sha256: str
    schema_map_sha256: str
    release_manifest_sha256: str
    schema_version: str = WITNESS_SCHEMA
