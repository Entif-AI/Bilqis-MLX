from __future__ import annotations

from dataclasses import asdict
import hashlib
import json

from ..frame_schema import (
    AtomicFrame, FrameInstance, FrameSchema, RoleOccurrence, SourceSpan,
)
from .common import ATOMIC_CODEC_ID, _canonical_bytes, _fail
from .metadata import ConstituentMetadata, ExtendedSlot, FrameSidecar
from .schema_tags import SchemaTagMap

def _extended_slot(binding: RoleOccurrence) -> ExtendedSlot:
    concepts = (
        (binding.concept,) if binding.concept is not None
        else binding.alternatives
    )
    child = binding.child_frame
    return ExtendedSlot(
        role_id=binding.role_id,
        occurrence_index=binding.occurrence_index,
        state=binding.state.value,
        abi_indices=tuple(item.abi_index for item in concepts),
        semantic_ids=tuple(item.semantic_id for item in concepts),
        child_occurrence_id=None if child is None else child.occurrence_id,
        child_content_digest=None if child is None else child.content_digest,
        child_type_ids=() if child is None else child.type_ids,
    )
def _constituent_metadata(
    order_index: int,
    binding: RoleOccurrence,
) -> ConstituentMetadata:
    concepts = (
        (binding.concept,) if binding.concept is not None
        else binding.alternatives
    )
    child = binding.child_frame
    return ConstituentMetadata(
        order_index=order_index,
        role_id=binding.role_id,
        occurrence_index=binding.occurrence_index,
        state=binding.state.value,
        semantic_ids=tuple(item.semantic_id for item in concepts),
        semantic_releases=tuple(item.semantic_release for item in concepts),
        abi_indices=tuple(item.abi_index for item in concepts),
        type_ids=tuple(item.type_ids for item in concepts),
        source_references=tuple(item.source_reference for item in concepts),
        child_occurrence_id=None if child is None else child.occurrence_id,
        child_content_digest=None if child is None else child.content_digest,
        child_type_ids=() if child is None else child.type_ids,
    )
def _frame_sidecar(
    frame: FrameInstance | AtomicFrame,
    schema: FrameSchema | None,
    schema_map: SchemaTagMap,
    codec_id: str,
    frame_payload: bytes,
) -> FrameSidecar:
    if isinstance(frame, AtomicFrame):
        return FrameSidecar(
            codec_id=codec_id,
            semantic_release=schema_map.semantic_release,
            schema_map_sha256=schema_map.digest,
            schema_id=None,
            schema_revision=None,
            schema_sha256=None,
            ast_construct=frame.ast_construct,
            order_mode=None,
            scope=None,
            occurrence_id=frame.occurrence_id,
            content_digest=frame.content_digest,
            source_instance_id=frame.source_instance_id,
            structural_path=frame.structural_path,
            source_span=frame.source_span,
            parent_occurrence_id=frame.parent_occurrence_id,
            causal_prefix_end=frame.causal_prefix_end,
            constituents=(),
            frame_payload_sha256=hashlib.sha256(frame_payload).hexdigest(),
        )
    if not isinstance(schema, FrameSchema):
        _fail("FRAME_SCHEMA_SIDECAR_REQUIRED")
    return FrameSidecar(
        codec_id=codec_id,
        semantic_release=schema_map.semantic_release,
        schema_map_sha256=schema_map.digest,
        schema_id=schema.schema_id,
        schema_revision=schema.revision,
        schema_sha256=hashlib.sha256(schema.canonical_bytes()).hexdigest(),
        ast_construct=schema.ast_construct,
        order_mode=schema.order_mode,
        scope=schema.scope,
        occurrence_id=frame.occurrence_id,
        content_digest=frame.content_digest,
        source_instance_id=frame.source_instance_id,
        structural_path=frame.structural_path,
        source_span=frame.source_span,
        parent_occurrence_id=frame.parent_occurrence_id,
        causal_prefix_end=frame.causal_prefix_end,
        constituents=tuple(
            _constituent_metadata(index, binding)
            for index, binding in enumerate(frame.bindings)
        ),
        frame_payload_sha256=hashlib.sha256(frame_payload).hexdigest(),
    )
def _atomic_payload(frame: AtomicFrame) -> bytes:
    return _canonical_bytes(asdict(frame))
def _atomic_from_payload(payload: bytes) -> AtomicFrame:
    try:
        value = json.loads(payload)
        source_span = SourceSpan(**value["source_span"])
        frame = AtomicFrame(
            occurrence_id=value["occurrence_id"],
            content_digest=value["content_digest"],
            source_instance_id=value["source_instance_id"],
            structural_path=tuple(value["structural_path"]),
            source_span=source_span,
            parent_occurrence_id=value["parent_occurrence_id"],
            ast_construct=value["ast_construct"],
            source_payload=value["source_payload"],
            causal_prefix_end=value["causal_prefix_end"],
            schema_version=value["schema_version"],
        )
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        _fail("FRAME_ATOMIC_PAYLOAD_INVALID:" + type(error).__name__)
    if _atomic_payload(frame) != payload:
        _fail("FRAME_ATOMIC_PAYLOAD_NONCANONICAL")
    return frame
