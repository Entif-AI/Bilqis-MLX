"""Frame codec sidecars."""
from __future__ import annotations

import hashlib

from ..frame_schema import AtomicFrame, FrameInstance, FrameSchema, RoleOccurrence
from .primitives import _fail
from .schema_tags import SchemaTagMap
from .records import ExtendedSlot, ConstituentMetadata, FrameSidecar


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
