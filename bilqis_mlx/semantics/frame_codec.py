"""Reversible compact and extended encodings for released semantic frames."""

from __future__ import annotations

from .frame_codec_parts.common import (
    ATOMIC_CODEC_ID, CODEC_VERSION, COMPACT_CODEC_ID, EXTENDED_CODEC_ID,
    PRESENCE_MASK, PRESENCE_SHIFT, SCHEMA_SHIFT, VERSION_SHIFT,
    FallbackReason, PackDisposition, _canonical_bytes,
)
from .frame_codec_parts.schema_tags import (
    CompactFrameBytes, SchemaTagEntry, SchemaTagMap, SlotTuple,
)
from .frame_codec_parts.metadata import (
    ConstituentMetadata, ExtendedSlot, FrameSidecar,
)
from .frame_codec_parts.packed import PackDecision, PackedFrame
from .frame_codec_parts.compact import pack4, unpack4, serialize_u64, deserialize_u64
from .frame_codec_parts.classification import classify_frame
from .frame_codec_parts.pack import pack_frame
from .frame_codec_parts.unpack import role_index, unpack_frame

_PUBLIC_OBJECTS = (
    FallbackReason,
    PackDisposition,
    CompactFrameBytes,
    SchemaTagEntry,
    SchemaTagMap,
    SlotTuple,
    ConstituentMetadata,
    ExtendedSlot,
    FrameSidecar,
    PackDecision,
    PackedFrame,
    pack4,
    unpack4,
    serialize_u64,
    deserialize_u64,
    classify_frame,
    pack_frame,
    role_index,
    unpack_frame,
    _canonical_bytes,
)
for _public_object in _PUBLIC_OBJECTS:
    _public_object.__module__ = __name__
del _public_object

__all__ = (
    "ATOMIC_CODEC_ID", "CODEC_VERSION", "COMPACT_CODEC_ID", "EXTENDED_CODEC_ID",
    "PRESENCE_MASK", "PRESENCE_SHIFT", "SCHEMA_SHIFT", "VERSION_SHIFT",
    "FallbackReason", "PackDisposition", "CompactFrameBytes", "SchemaTagEntry",
    "SchemaTagMap", "SlotTuple", "ConstituentMetadata", "ExtendedSlot",
    "FrameSidecar", "PackDecision", "PackedFrame", "pack4", "unpack4",
    "serialize_u64", "deserialize_u64", "classify_frame", "pack_frame",
    "role_index", "unpack_frame", "_canonical_bytes",
)
