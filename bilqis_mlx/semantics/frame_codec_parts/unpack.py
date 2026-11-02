from __future__ import annotations

import hashlib
import json

from ..atlas_projection import FrozenAtlasSnapshot
from ..frame_schema import (
    AtomicFrame, BindingState, FrameInstance, FrameSchema, RoleSpec,
    frame_instance_from_bytes,
)
from .classification import _validate_frame_schema_shape
from .common import PackDisposition, _fail
from .compact import unpack4
from .metadata import ExtendedSlot
from .packed import PackedFrame
from .payload import _atomic_from_payload, _extended_slot, _frame_sidecar
from .schema_tags import SchemaTagMap

def _validate_schema_sidecar(
    packed: PackedFrame,
    schema_map: SchemaTagMap,
) -> FrameSchema | None:
    if packed.semantic_release != schema_map.semantic_release:
        _fail("FRAME_PACKED_RELEASE_MISMATCH")
    if packed.schema_map_sha256 != schema_map.digest:
        _fail("FRAME_PACKED_SCHEMA_MAP_MISMATCH")
    if packed.disposition is PackDisposition.ATOMIC:
        return None
    try:
        value = json.loads(packed.schema_payload)
        schema = FrameSchema(
            schema_id=value["schema_id"],
            revision=value["revision"],
            ast_construct=value["ast_construct"],
            roles=tuple(
                RoleSpec(
                    role_id=item["role_id"],
                    allowed_type_ids=tuple(item["allowed_type_ids"]),
                    min_cardinality=item["min_cardinality"],
                    max_cardinality=item["max_cardinality"],
                    schema_version=item["schema_version"],
                )
                for item in value["roles"]
            ),
            order_mode=value["order_mode"],
            scope=value["scope"],
            ast_contract_sha256=value.get("ast_contract_sha256"),
            schema_version=value["schema_version"],
        )
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        _fail("FRAME_PACKED_SCHEMA_PAYLOAD_INVALID:" + type(error).__name__)
    canonical = schema.canonical_bytes()
    if (canonical != packed.schema_payload
            or hashlib.sha256(canonical).hexdigest() != packed.schema_sha256
            or (schema.schema_id, schema.revision)
            != (packed.schema_id, packed.schema_revision)):
        _fail("FRAME_PACKED_SCHEMA_IDENTITY_MISMATCH")
    if packed.disposition is PackDisposition.COMPACT:
        decoded = unpack4(packed.compact_word, schema_map)
        if ((decoded.schema.schema_id, decoded.schema.schema_revision,
             decoded.schema.schema_sha256)
                != (schema.schema_id, schema.revision, packed.schema_sha256)):
            _fail("FRAME_PACKED_COMPACT_SCHEMA_MISMATCH")
    return schema
def _validate_extended_slots(
    frame: FrameInstance,
    slots: tuple[ExtendedSlot, ...],
) -> None:
    expected = tuple(_extended_slot(binding) for binding in frame.bindings)
    if slots != expected:
        _fail("FRAME_EXTENDED_SLOT_SIDECAR_MISMATCH")
def _validate_frame_sidecar(
    packed: PackedFrame,
    frame: FrameInstance | AtomicFrame,
    schema: FrameSchema | None,
    schema_map: SchemaTagMap,
) -> None:
    if isinstance(frame, FrameInstance):
        if schema is None or (
            frame.frame_schema_id,
            frame.frame_schema_revision,
        ) != (schema.schema_id, schema.revision):
            _fail("FRAME_PACKED_FRAME_SCHEMA_MISMATCH")
        _validate_frame_schema_shape(frame, schema)
        for binding in frame.bindings:
            concepts = (
                (binding.concept,) if binding.concept is not None
                else binding.alternatives
            )
            if any(item.semantic_release != packed.semantic_release
                   for item in concepts):
                _fail("FRAME_PACKED_FRAME_RELEASE_MISMATCH")
    expected = _frame_sidecar(
        frame,
        schema,
        schema_map,
        packed.codec_id,
        packed.frame_payload,
    )
    if packed.sidecar != expected:
        _fail("FRAME_CODEC_SIDECAR_MISMATCH")
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
def role_index(
    packed: PackedFrame,
    role_id: str,
    occurrence_index: int,
    *,
    schema_map: SchemaTagMap,
    snapshot: FrozenAtlasSnapshot,
) -> int:
    """Return one neural-readout ABI index through the same path for both codecs."""
    frame = unpack_frame(packed, schema_map=schema_map)
    if not isinstance(frame, FrameInstance):
        _fail("FRAME_READOUT_ATOMIC_FORBIDDEN")
    match = next((
        binding for binding in frame.bindings
        if (binding.role_id, binding.occurrence_index)
        == (role_id, occurrence_index)
    ), None)
    if match is None:
        _fail("FRAME_READOUT_ROLE_UNKNOWN")
    if (match.state is not BindingState.VALUE
            or match.concept is None
            or match.child_frame is not None):
        _fail("FRAME_READOUT_SLOT_NONCONCEPT")
    concept = match.concept
    if (snapshot.release_sha256 != packed.semantic_release
            or concept.semantic_release != packed.semantic_release):
        _fail("FRAME_READOUT_RELEASE_MISMATCH")
    held_ids = {
        row.semantic_id for row in snapshot.source_hold_census()
        if row.semantic_id is not None
    }
    if concept.semantic_id in held_ids:
        _fail("FRAME_READOUT_SEMANTIC_HELD")
    lookup = dict(snapshot.semantic_lookup)
    if concept.semantic_id not in lookup:
        _fail("FRAME_READOUT_SEMANTIC_NOT_IN_ABI")
    index = lookup[concept.semantic_id]
    if index != concept.abi_index:
        _fail("FRAME_READOUT_ABI_INDEX_MISMATCH")
    authoritative_types = next(
        (item.concept.types for item in snapshot.concepts
         if item.concept.semantic_id == concept.semantic_id),
        None,
    )
    if (authoritative_types is not None
            and tuple(concept.type_ids) != tuple(authoritative_types)):
        _fail("FRAME_CONCEPT_TYPE_AUTHORITY_MISMATCH")
    entry = snapshot.abi(index)
    if not entry.active:
        _fail("FRAME_READOUT_INDEX_INACTIVE")
    return index
