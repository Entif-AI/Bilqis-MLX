"""Frame codec primitives."""
from __future__ import annotations

from enum import Enum
import hashlib
import json
import re

from ...errors import ErrorBus, SEMANTIC_FRAME


COMPACT_CODEC_ID = "bamf.frame-u64/v1"
SCHEMA_MAP_SCHEMA = "bilqis.frame-schema-tag-map/v1"
SCHEMA_TAG_ENTRY_SCHEMA = "bilqis.frame-schema-tag-entry/v1"
SLOT_TUPLE_SCHEMA = "bilqis.frame-slot-tuple/v1"
COMPACT_BYTES_SCHEMA = "bilqis.frame-u64-bytes/v1"
PACKED_FRAME_SCHEMA = "bilqis.packed-frame/v1"
EXTENDED_SLOT_SCHEMA = "bilqis.extended-frame-slot/v1"
FRAME_SIDECAR_SCHEMA = "bilqis.frame-codec-sidecar/v1"
CONSTITUENT_METADATA_SCHEMA = "bilqis.frame-constituent-metadata/v1"
EXTENDED_CODEC_ID = "bamf.frame-extended/v1"
ATOMIC_CODEC_ID = "bamf.frame-atomic/v1"
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
UINT32_BITS = 32
UINT32_LIMIT = 1 << UINT32_BITS
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



class PackDisposition(str, Enum):
    COMPACT = "COMPACT_V1"
    EXTENDED = "EXTENDED_V1"
    ATOMIC = "ATOMIC_V1"



class FallbackReason(str, Enum):
    COMPACT_ELIGIBLE = "COMPACT_ELIGIBLE"
    ATOMIC_FRAME = "ATOMIC_FRAME"
    SCHEMA_TAG_UNAVAILABLE = "SCHEMA_TAG_UNAVAILABLE"
    SCHEMA_NOT_FOUR_SINGULAR_ROLES = "SCHEMA_NOT_FOUR_SINGULAR_ROLES"
    SLOT_COUNT_NOT_FOUR = "SLOT_COUNT_NOT_FOUR"
    REPEATED_ROLE_OCCURRENCE = "REPEATED_ROLE_OCCURRENCE"
    NON_VALUE_BINDING = "NON_VALUE_BINDING"
    CHILD_FRAME = "CHILD_FRAME"
    INDEX_REQUIRES_UINT32 = "INDEX_REQUIRES_UINT32"
