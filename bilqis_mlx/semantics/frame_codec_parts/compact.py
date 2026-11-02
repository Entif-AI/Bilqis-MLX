from __future__ import annotations

from .common import (
    CODEC_VERSION, COMPACT_CODEC_ID, PRESENCE_MASK, PRESENCE_SHIFT, SCHEMA_LIMIT,
    SCHEMA_MASK, SCHEMA_SHIFT, SLOT_BITS, SLOT_COUNT, SLOT_LIMIT, SLOT_MASK,
    U64_BYTES, U64_LIMIT, VERSION_MASK, VERSION_SHIFT, _fail,
)
from .schema_tags import CompactFrameBytes, SchemaTagMap, SlotTuple

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
