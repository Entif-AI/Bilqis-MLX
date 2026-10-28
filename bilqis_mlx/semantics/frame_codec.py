"""Reversible compact and extended encodings for released semantic frames."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re

from ..errors import ErrorBus, SEMANTIC_FRAME
from .frame_schema import FrameSchema


COMPACT_CODEC_ID = "bamf.frame-u64/v1"
SCHEMA_MAP_SCHEMA = "bilqis.frame-schema-tag-map/v1"
SCHEMA_TAG_ENTRY_SCHEMA = "bilqis.frame-schema-tag-entry/v1"
SLOT_TUPLE_SCHEMA = "bilqis.frame-slot-tuple/v1"
COMPACT_BYTES_SCHEMA = "bilqis.frame-u64-bytes/v1"

SLOT_COUNT = 4
SLOT_BITS = 13
SLOT_LIMIT = 1 << SLOT_BITS
SLOT_MASK = SLOT_LIMIT - 1
PRESENCE_SHIFT = SLOT_COUNT * SLOT_BITS
PRESENCE_MASK = (1 << SLOT_COUNT) - 1
SCHEMA_SHIFT = PRESENCE_SHIFT + SLOT_COUNT
SCHEMA_BITS = 4
SCHEMA_LIMIT = 1 << SCHEMA_BITS
SCHEMA_MASK = SCHEMA_LIMIT - 1
VERSION_SHIFT = SCHEMA_SHIFT + SCHEMA_BITS
VERSION_BITS = 4
VERSION_MASK = (1 << VERSION_BITS) - 1
CODEC_VERSION = 1
U64_BITS = 64
U64_LIMIT = 1 << U64_BITS
U64_BYTES = 8

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _fail(reason: str) -> None:
    ErrorBus.raise_(SEMANTIC_FRAME.CODEC.INVALID, reason=reason)


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n").encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


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


@dataclass(frozen=True)
class SlotTuple:
    indices: tuple[int, int, int, int]
    schema_tag: int
    schema: SchemaTagEntry
    presence_mask: int = PRESENCE_MASK
    codec_version: int = CODEC_VERSION
    codec_id: str = COMPACT_CODEC_ID
    schema_version: str = SLOT_TUPLE_SCHEMA

    def __post_init__(self) -> None:
        if (len(self.indices) != SLOT_COUNT
                or any(type(index) is not int or not 0 <= index < SLOT_LIMIT
                       for index in self.indices)
                or self.schema_tag != self.schema.tag
                or self.presence_mask != PRESENCE_MASK
                or self.codec_version != CODEC_VERSION
                or self.codec_id != COMPACT_CODEC_ID
                or self.schema_version != SLOT_TUPLE_SCHEMA):
            _fail("FRAME_SLOT_TUPLE_INVALID")


@dataclass(frozen=True)
class CompactFrameBytes:
    codec_id: str
    payload: bytes
    word_decimal: str
    schema_version: str = COMPACT_BYTES_SCHEMA

    def __post_init__(self) -> None:
        if (self.codec_id != COMPACT_CODEC_ID
                or not isinstance(self.payload, bytes)
                or len(self.payload) != U64_BYTES
                or not isinstance(self.word_decimal, str)
                or not self.word_decimal.isdecimal()
                or self.schema_version != COMPACT_BYTES_SCHEMA):
            _fail("FRAME_COMPACT_BYTES_INVALID")
        word = int.from_bytes(self.payload, "little", signed=False)
        if str(word) != self.word_decimal:
            _fail("FRAME_COMPACT_BYTES_WORD_MISMATCH")

    def json_value(self) -> dict[str, str]:
        return {
            "codec_id": self.codec_id,
            "word_decimal": self.word_decimal,
            "little_endian_hex": self.payload.hex(),
        }


def pack4(indices: tuple[int, int, int, int], schema_tag: int) -> int:
    """Pack four complete 13-bit semantic indices into the exact BAMF v1 u64."""
    if not isinstance(indices, tuple) or len(indices) != SLOT_COUNT:
        _fail("FRAME_COMPACT_SLOT_COUNT_INVALID")
    if any(type(index) is not int or not 0 <= index < SLOT_LIMIT
           for index in indices):
        _fail("FRAME_COMPACT_INDEX_OUT_OF_RANGE")
    if type(schema_tag) is not int or not 0 <= schema_tag < SCHEMA_LIMIT:
        _fail("FRAME_COMPACT_SCHEMA_TAG_OUT_OF_RANGE")
    word = 0
    for slot, index in enumerate(indices):
        word |= index << (slot * SLOT_BITS)
    word |= PRESENCE_MASK << PRESENCE_SHIFT
    word |= schema_tag << SCHEMA_SHIFT
    word |= CODEC_VERSION << VERSION_SHIFT
    return word


def unpack4(word: int, schema_map: SchemaTagMap) -> SlotTuple:
    """Decode one exact compact word and bind its tag to one release-local schema."""
    if type(word) is not int or not 0 <= word < U64_LIMIT:
        _fail("FRAME_COMPACT_WORD_OUT_OF_RANGE")
    if not isinstance(schema_map, SchemaTagMap):
        _fail("FRAME_SCHEMA_TAG_MAP_REQUIRED")
    version = (word >> VERSION_SHIFT) & VERSION_MASK
    if version != CODEC_VERSION:
        _fail("FRAME_COMPACT_VERSION_MISMATCH")
    presence = (word >> PRESENCE_SHIFT) & PRESENCE_MASK
    if presence != PRESENCE_MASK:
        _fail("FRAME_COMPACT_PRESENCE_INVALID")
    schema_tag = (word >> SCHEMA_SHIFT) & SCHEMA_MASK
    schema = schema_map.resolve(schema_tag)
    indices = tuple(
        (word >> (slot * SLOT_BITS)) & SLOT_MASK
        for slot in range(SLOT_COUNT)
    )
    return SlotTuple(indices, schema_tag, schema)


def serialize_u64(word: int) -> CompactFrameBytes:
    if type(word) is not int or not 0 <= word < U64_LIMIT:
        _fail("FRAME_COMPACT_WORD_OUT_OF_RANGE")
    payload = word.to_bytes(U64_BYTES, "little", signed=False)
    return CompactFrameBytes(COMPACT_CODEC_ID, payload, str(word))


def deserialize_u64(encoded: CompactFrameBytes) -> int:
    if not isinstance(encoded, CompactFrameBytes):
        _fail("FRAME_COMPACT_BYTES_REQUIRED")
    return int.from_bytes(encoded.payload, "little", signed=False)
