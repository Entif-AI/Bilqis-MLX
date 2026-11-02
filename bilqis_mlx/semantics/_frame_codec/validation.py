"""Frame codec validation."""
from __future__ import annotations

import hashlib
import json

from ..frame_schema import AtomicFrame, FrameInstance, FrameSchema, RoleSpec
from .primitives import _fail, PackDisposition
from .schema_tags import SchemaTagMap
from .compact import unpack4
from .records import ExtendedSlot
from .packed import PackedFrame
from .classification import _validate_frame_schema_shape
from .sidecars import _extended_slot, _frame_sidecar


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
