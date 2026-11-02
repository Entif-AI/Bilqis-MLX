"""Reversible compact and extended encodings for released semantic frames."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import re

from ..errors import ErrorBus, SEMANTIC_FRAME
from .atlas_projection import FrozenAtlasSnapshot
from .frame_schema import (
    AtomicFrame,
    BindingState,
    ChildFrameRef,
    ConceptRef,
    FrameInstance,
    FrameSchema,
    RoleOccurrence,
    RoleSpec,
    SourceSpan,
    frame_instance_from_bytes,
)

from ._frame_codec.primitives import (
    _fail, _canonical_bytes, _digest,
    PackDisposition, FallbackReason, COMPACT_CODEC_ID,
    SCHEMA_MAP_SCHEMA, SCHEMA_TAG_ENTRY_SCHEMA, SLOT_TUPLE_SCHEMA,
    COMPACT_BYTES_SCHEMA, PACKED_FRAME_SCHEMA, EXTENDED_SLOT_SCHEMA,
    FRAME_SIDECAR_SCHEMA, CONSTITUENT_METADATA_SCHEMA, EXTENDED_CODEC_ID,
    ATOMIC_CODEC_ID, SLOT_COUNT, SLOT_BITS,
    SLOT_LIMIT, SLOT_MASK, PRESENCE_SHIFT,
    PRESENCE_MASK, SCHEMA_SHIFT, SCHEMA_BITS,
    SCHEMA_LIMIT, SCHEMA_MASK, VERSION_SHIFT,
    VERSION_BITS, VERSION_MASK, CODEC_VERSION,
    U64_BITS, U64_LIMIT, U64_BYTES,
    UINT32_BITS, UINT32_LIMIT, _SHA256,
)
from ._frame_codec.schema_tags import (
    SchemaTagEntry, SchemaTagMap,
)
from ._frame_codec.compact import (
    SlotTuple, CompactFrameBytes, pack4,
    unpack4, serialize_u64, deserialize_u64,
)
from ._frame_codec.records import (
    ExtendedSlot, ConstituentMetadata, FrameSidecar,
)
from ._frame_codec.packed import (
    PackDecision, PackedFrame,
)
from ._frame_codec.classification import (
    _frame_semantic_release, _validate_frame_schema_shape, classify_frame,
)
from ._frame_codec.sidecars import (
    _extended_slot, _constituent_metadata, _frame_sidecar,
)
from ._frame_codec.atomic import (
    _atomic_payload, _atomic_from_payload,
)
from ._frame_codec.packing import (
    pack_frame,
)
from ._frame_codec.validation import (
    _validate_schema_sidecar, _validate_extended_slots, _validate_frame_sidecar,
)
from ._frame_codec.unpacking import (
    unpack_frame,
)
from ._frame_codec.readout import (
    role_index,
)




# Preserve canonical identities for frame-codec public contracts.
for _public in (
    _fail, _canonical_bytes, _digest,
    PackDisposition, FallbackReason, SchemaTagEntry,
    SchemaTagMap, SlotTuple, CompactFrameBytes,
    pack4, unpack4, serialize_u64,
    deserialize_u64, ExtendedSlot, ConstituentMetadata,
    FrameSidecar, PackDecision, PackedFrame,
    _frame_semantic_release, _validate_frame_schema_shape, classify_frame,
    _extended_slot, _constituent_metadata, _frame_sidecar,
    _atomic_payload, _atomic_from_payload, pack_frame,
    _validate_schema_sidecar, _validate_extended_slots, _validate_frame_sidecar,
    unpack_frame, role_index,
):
    _public.__module__ = __name__
