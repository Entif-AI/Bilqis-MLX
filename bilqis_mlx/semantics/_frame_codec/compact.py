"""Frame codec compact."""
from __future__ import annotations

from dataclasses import dataclass

from .primitives import (
    _fail, COMPACT_CODEC_ID, SLOT_TUPLE_SCHEMA, COMPACT_BYTES_SCHEMA, SLOT_COUNT,
    SLOT_BITS, SLOT_LIMIT, SLOT_MASK, PRESENCE_SHIFT, PRESENCE_MASK, SCHEMA_SHIFT,
    SCHEMA_LIMIT, SCHEMA_MASK, VERSION_SHIFT, VERSION_MASK, CODEC_VERSION,
    U64_LIMIT, U64_BYTES,
)
from .schema_tags import SchemaTagEntry, SchemaTagMap


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
