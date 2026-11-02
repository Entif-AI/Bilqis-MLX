"""Frame codec unpacking."""
from __future__ import annotations

from ..frame_schema import AtomicFrame, FrameInstance, frame_instance_from_bytes
from .primitives import _fail, PackDisposition
from .schema_tags import SchemaTagMap
from .compact import unpack4
from .packed import PackedFrame
from .atomic import _atomic_from_payload
from .validation import (
    _validate_schema_sidecar, _validate_extended_slots, _validate_frame_sidecar,
)


def unpack_frame(
    packed: PackedFrame,
    *,
    schema_map: SchemaTagMap,
) -> FrameInstance | AtomicFrame:
    if not isinstance(packed, PackedFrame):
        _fail("FRAME_PACKED_RECORD_REQUIRED")
    schema = _validate_schema_sidecar(packed, schema_map)
    if packed.disposition is PackDisposition.ATOMIC:
        frame = _atomic_from_payload(packed.frame_payload)
        _validate_frame_sidecar(packed, frame, None, schema_map)
        return frame
    frame = frame_instance_from_bytes(packed.frame_payload)
    if packed.disposition is PackDisposition.COMPACT:
        decoded = unpack4(packed.compact_word, schema_map)
        sidecar_indices = tuple(
            binding.concept.abi_index for binding in frame.bindings)
        if decoded.indices != sidecar_indices:
            _fail("FRAME_COMPACT_SLOT_SIDECAR_MISMATCH")
    else:
        _validate_extended_slots(frame, packed.extended_slots)
    _validate_frame_sidecar(packed, frame, schema, schema_map)
    return frame
