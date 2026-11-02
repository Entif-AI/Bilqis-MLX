"""Frame codec schema_tags."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib

from ..frame_schema import FrameSchema
from .primitives import (
    _fail, _digest, SCHEMA_MAP_SCHEMA, SCHEMA_TAG_ENTRY_SCHEMA, SCHEMA_LIMIT,
    _SHA256,
)


@dataclass(frozen=True, order=True)
class SchemaTagEntry:
    tag: int
    schema_id: str
    schema_revision: int
    schema_sha256: str
    schema_version: str = SCHEMA_TAG_ENTRY_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.tag) is not int or not 0 <= self.tag < SCHEMA_LIMIT
                or not isinstance(self.schema_id, str) or not self.schema_id
                or type(self.schema_revision) is not int or self.schema_revision < 1
                or not _SHA256.fullmatch(self.schema_sha256)
                or self.schema_version != SCHEMA_TAG_ENTRY_SCHEMA):
            _fail("FRAME_SCHEMA_TAG_ENTRY_INVALID")



@dataclass(frozen=True)
class SchemaTagMap:
    semantic_release: str
    entries: tuple[SchemaTagEntry, ...]
    schema_version: str = SCHEMA_MAP_SCHEMA

    def __post_init__(self) -> None:
        tags = tuple(item.tag for item in self.entries)
        identities = tuple(
            (item.schema_id, item.schema_revision) for item in self.entries)
        if (not _SHA256.fullmatch(self.semantic_release)
                or self.entries != tuple(sorted(self.entries))
                or len(tags) != len(set(tags))
                or len(identities) != len(set(identities))
                or self.schema_version != SCHEMA_MAP_SCHEMA):
            _fail("FRAME_SCHEMA_TAG_MAP_INVALID")

    @classmethod
    def from_schemas(
        cls,
        semantic_release: str,
        schemas: tuple[FrameSchema, ...],
    ) -> "SchemaTagMap":
        ordered = tuple(sorted(
            schemas,
            key=lambda item: (
                item.schema_id.encode("utf-8"),
                item.revision,
                hashlib.sha256(item.canonical_bytes()).digest(),
            ),
        ))
        if len(ordered) > SCHEMA_LIMIT:
            _fail("FRAME_SCHEMA_TAG_CAPACITY_EXCEEDED")
        identities = tuple((item.schema_id, item.revision) for item in ordered)
        if len(identities) != len(set(identities)):
            _fail("FRAME_SCHEMA_TAG_IDENTITY_DUPLICATE")
        return cls(
            semantic_release=semantic_release,
            entries=tuple(
                SchemaTagEntry(
                    tag=index,
                    schema_id=schema.schema_id,
                    schema_revision=schema.revision,
                    schema_sha256=hashlib.sha256(schema.canonical_bytes()).hexdigest(),
                )
                for index, schema in enumerate(ordered)
            ),
        )

    @property
    def digest(self) -> str:
        return _digest(asdict(self))

    def resolve(self, tag: int) -> SchemaTagEntry:
        if type(tag) is not int:
            _fail("FRAME_SCHEMA_TAG_INVALID")
        match = next((item for item in self.entries if item.tag == tag), None)
        if match is None:
            _fail("FRAME_SCHEMA_TAG_UNKNOWN")
        return match

    def tag_for(self, schema: FrameSchema) -> int | None:
        digest = hashlib.sha256(schema.canonical_bytes()).hexdigest()
        match = next((
            item for item in self.entries
            if item.schema_id == schema.schema_id
            and item.schema_revision == schema.revision
            and item.schema_sha256 == digest
        ), None)
        return None if match is None else match.tag
