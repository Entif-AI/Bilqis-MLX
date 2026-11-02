from __future__ import annotations

import hashlib

from ..frame_schema import AtomicFrame, FrameInstance, FrameSchema
from .classification import classify_frame
from .common import ATOMIC_CODEC_ID, COMPACT_CODEC_ID, EXTENDED_CODEC_ID, PackDisposition
from .compact import pack4
from .packed import PackedFrame
from .payload import _atomic_payload, _extended_slot, _frame_sidecar
from .schema_tags import SchemaTagMap

def pack_frame(
    frame: FrameInstance | AtomicFrame,
    *,
    schema: FrameSchema | None,
    schema_map: SchemaTagMap,
) -> PackedFrame:
    """Pack a frame for storage; source admission remains a readout concern."""
    decision = classify_frame(frame, schema, schema_map)
    if decision.disposition is PackDisposition.ATOMIC:
        frame_payload = _atomic_payload(frame)
        sidecar = _frame_sidecar(
            frame, None, schema_map, ATOMIC_CODEC_ID, frame_payload)
        return PackedFrame(
            disposition=decision.disposition,
            reason=decision.reason,
            codec_id=ATOMIC_CODEC_ID,
            semantic_release=schema_map.semantic_release,
            schema_map_sha256=schema_map.digest,
            schema_id=None,
            schema_revision=None,
            schema_sha256=None,
            schema_payload=None,
            frame_payload=frame_payload,
            compact_word=None,
            extended_slots=(),
            sidecar=sidecar,
        )

    schema_payload = schema.canonical_bytes()
    schema_sha256 = hashlib.sha256(schema_payload).hexdigest()
    frame_payload = frame.canonical_bytes()
    if decision.disposition is PackDisposition.COMPACT:
        indices = tuple(binding.concept.abi_index for binding in frame.bindings)
        word = pack4(indices, decision.schema_tag)
        sidecar = _frame_sidecar(
            frame, schema, schema_map, COMPACT_CODEC_ID, frame_payload)
        return PackedFrame(
            disposition=decision.disposition,
            reason=decision.reason,
            codec_id=COMPACT_CODEC_ID,
            semantic_release=schema_map.semantic_release,
            schema_map_sha256=schema_map.digest,
            schema_id=schema.schema_id,
            schema_revision=schema.revision,
            schema_sha256=schema_sha256,
            schema_payload=schema_payload,
            frame_payload=frame_payload,
            compact_word=word,
            extended_slots=(),
            sidecar=sidecar,
        )
    slots = tuple(_extended_slot(binding) for binding in frame.bindings)
    sidecar = _frame_sidecar(
        frame, schema, schema_map, EXTENDED_CODEC_ID, frame_payload)
    return PackedFrame(
        disposition=decision.disposition,
        reason=decision.reason,
        codec_id=EXTENDED_CODEC_ID,
        semantic_release=schema_map.semantic_release,
        schema_map_sha256=schema_map.digest,
        schema_id=schema.schema_id,
        schema_revision=schema.revision,
        schema_sha256=schema_sha256,
        schema_payload=schema_payload,
        frame_payload=frame_payload,
        compact_word=None,
        extended_slots=slots,
        sidecar=sidecar,
    )
