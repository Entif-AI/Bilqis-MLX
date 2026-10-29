"""A03 source-release frame-schema body witnesses.

The issuer freezes the existing FrameSchema bodies and SchemaTagMap; it does
not define a second schema registry. A consumer must load the frozen bytes
against the digest supplied by the accepted A03 release, never a digest
invented alongside an untrusted candidate schema.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
from pathlib import Path
import re

from ..errors import BilqisError, ErrorBus, SEMANTIC_FRAME
from .atlas_projection import FrozenAtlasSnapshot
from .atlas.snapshot import AtlasArtifactSelection, load_pinned_atlas_snapshot
from .frame_codec import (
    SchemaTagEntry, SchemaTagMap, _canonical_bytes,
)
from .frame_schema import FrameSchema, frame_schema_from_bytes


MANIFEST_SCHEMA = "bilqis.released-frame-schema-manifest/v1"
BODY_SCHEMA = "bilqis.released-frame-schema-body/v1"
WITNESS_SCHEMA = "bilqis.released-frame-schema-body-witness/v1"
SOURCE_PIN_REGISTRY_SCHEMA = "bilqis.frame-schema-source-pins/v1"
SOURCE_PIN_REGISTRY_SHA256 = (
    "4c8da914834f8dc5cadef67bbf9b7da1031f07cc80d4775a47d18b68af62a6c1")
SOURCE_PIN_STATUS = "A03_SOURCE_ATTESTED_NOT_NEURAL_ADMITTED"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _fail(reason: str) -> None:
    ErrorBus.raise_(SEMANTIC_FRAME.CODEC.INVALID, reason=reason)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("FRAME_RELEASED_SCHEMA_JSON_DUPLICATE_KEY")
        result[key] = value
    return result


def _json(payload: bytes) -> dict:
    if not isinstance(payload, bytes):
        _fail("FRAME_RELEASED_SCHEMA_BYTES_REQUIRED")
    try:
        value = json.loads(payload, object_pairs_hook=_unique_pairs)
    except BilqisError:
        raise
    except (ValueError, UnicodeError, TypeError):
        _fail("FRAME_RELEASED_SCHEMA_JSON_INVALID")
    if not isinstance(value, dict):
        _fail("FRAME_RELEASED_SCHEMA_JSON_INVALID")
    return value


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


def _source_pins() -> tuple[dict, ...]:
    """Repository-owned pin ledger, itself hash-pinned like the A01 registry."""
    path = Path(__file__).with_name("frame_schema_source_pins_v1.json")
    if path.is_symlink() or not path.is_file():
        _fail("FRAME_RELEASED_SOURCE_PIN_REGISTRY_MISSING")
    try:
        payload = path.read_bytes()
    except OSError:
        _fail("FRAME_RELEASED_SOURCE_PIN_REGISTRY_MISSING")
    if not hmac.compare_digest(_sha(payload), SOURCE_PIN_REGISTRY_SHA256):
        _fail("FRAME_RELEASED_SOURCE_PIN_REGISTRY_INVALID")
    registry = _json(payload)
    if (set(registry) != {"schema", "entries"}
            or registry["schema"] != SOURCE_PIN_REGISTRY_SCHEMA
            or payload != _canonical_bytes(registry)
            or not isinstance(registry["entries"], list)
            or not registry["entries"]):
        _fail("FRAME_RELEASED_SOURCE_PIN_REGISTRY_INVALID")
    required = {
        "family", "semantic_release", "atlas_bundle_id",
        "source_bundle_id", "schema_manifest_sha256",
        "schema_map_sha256", "source_receipt", "status"}
    for entry in registry["entries"]:
        if (not isinstance(entry, dict) or set(entry) != required
                or not isinstance(entry["family"], str)
                or not entry["family"]
                or any(not isinstance(entry[name], str)
                       or not _SHA.fullmatch(entry[name])
                       for name in (
                           "semantic_release", "atlas_bundle_id",
                           "source_bundle_id", "schema_manifest_sha256",
                           "schema_map_sha256"))
                or entry["status"] != SOURCE_PIN_STATUS
                or entry["source_receipt"]
                != "docs/evidence/bamf/A03.4/receipt.md"):
            _fail("FRAME_RELEASED_SOURCE_PIN_REGISTRY_INVALID")
    entries = tuple(registry["entries"])
    if len({(entry["family"], entry["semantic_release"])
            for entry in entries}) != len(entries):
        _fail("FRAME_RELEASED_SOURCE_PIN_REGISTRY_INVALID")
    return entries


def _load_pinned_released_frame_schemas(
    source_family: str, atlas_selection: AtlasArtifactSelection,
) -> VerifiedReleasedFrameSchemas:
    """Offline source-owner lookup; no caller-supplied schema registry or hash."""
    if not isinstance(source_family, str) or not source_family:
        _fail("FRAME_RELEASED_SOURCE_FAMILY_INVALID")
    # The A01 source pin is checked against its own independent repository
    # ledger before any A03 schema manifest can gain consumer authority.
    snapshot = load_pinned_atlas_snapshot(atlas_selection)
    matches = tuple(entry for entry in _source_pins()
                    if entry["family"] == source_family
                    and entry["semantic_release"] == snapshot.release_sha256
                    and entry["atlas_bundle_id"] == snapshot.bundle_id
                    and entry["source_bundle_id"] == snapshot.source_bundle_id)
    if len(matches) != 1:
        _fail("FRAME_RELEASED_SOURCE_PIN_NOT_REGISTERED")
    entry = matches[0]
    path = Path(__file__).with_name("frame_schema_releases") / (
        "frame-schemas-" + entry["schema_manifest_sha256"] + ".json")
    if path.is_symlink() or not path.is_file():
        _fail("FRAME_RELEASED_MANIFEST_SOURCE_MISSING")
    try:
        payload = path.read_bytes()
    except OSError:
        _fail("FRAME_RELEASED_MANIFEST_SOURCE_MISSING")
    return load_released_frame_schemas(
        payload, expected_sha256=entry["schema_manifest_sha256"],
        snapshot=snapshot,
        expected_semantic_release=entry["semantic_release"],
        expected_schema_map_sha256=entry["schema_map_sha256"])


def lookup_source_pinned_frame_schema(
    schema_id: str, revision: int, *,
    source_family: str, atlas_selection: AtlasArtifactSelection,
) -> tuple[FrameSchema, ReleasedSchemaBodyWitness]:
    """Resolve an A03 body from repo pins, never from a caller-provided registry."""
    pinned = _load_pinned_released_frame_schemas(
        source_family, atlas_selection)
    witness = pinned.lookup(schema_id, revision)
    body = next(item for item in pinned.manifest.bodies
                if (item.schema_id, item.revision)
                == (schema_id, revision))
    return pinned.require_schema(body.parse(), witness), witness


def verify_source_pinned_frame_schema(
    candidate: FrameSchema, *,
    source_family: str, atlas_selection: AtlasArtifactSelection,
) -> FrameSchema:
    """Production gate: re-enter A01/A03 pins on every candidate verification."""
    if type(candidate) is not FrameSchema:
        _fail("FRAME_RELEASED_SCHEMA_BODY_INVALID")
    canonical, _ = lookup_source_pinned_frame_schema(
        candidate.schema_id, candidate.revision,
        source_family=source_family, atlas_selection=atlas_selection)
    if candidate.canonical_bytes() != canonical.canonical_bytes():
        _fail("FRAME_RELEASED_SCHEMA_BODY_MISMATCH")
    return canonical


def verify_source_pinned_frame_schema_bytes(
    payload: bytes, *,
    source_family: str, atlas_selection: AtlasArtifactSelection,
) -> FrameSchema:
    """JSON key order is ignored, but source-pinned role order and body are not."""
    candidate = frame_schema_from_bytes(_canonical_bytes(_json(payload)))
    return verify_source_pinned_frame_schema(
        candidate, source_family=source_family,
        atlas_selection=atlas_selection)
