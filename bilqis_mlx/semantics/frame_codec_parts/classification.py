from __future__ import annotations

from ..frame_schema import AtomicFrame, BindingState, FrameInstance, FrameSchema
from .common import FallbackReason, PackDisposition, SLOT_COUNT, SLOT_LIMIT, _fail
from .packed import PackDecision
from .schema_tags import SchemaTagMap

def _frame_semantic_release(
    frame: FrameInstance,
    schema_map: SchemaTagMap,
) -> str:
    releases = {
        concept.semantic_release
        for binding in frame.bindings
        for concept in (
            *((binding.concept,) if binding.concept is not None else ()),
            *binding.alternatives,
        )
    }
    if releases and releases != {schema_map.semantic_release}:
        _fail("FRAME_PACKED_SEMANTIC_RELEASE_MISMATCH")
    return schema_map.semantic_release
def _validate_frame_schema_shape(frame: FrameInstance, schema: FrameSchema) -> None:
    """Representation fallback never overrides an authoritative role contract."""
    if frame.schema_role_order != tuple(role.role_id for role in schema.roles):
        _fail("FRAME_PACKED_FRAME_SCHEMA_ROLE_ORDER_MISMATCH")
    role_map = {role.role_id: role for role in schema.roles}
    if any(binding.role_id not in role_map for binding in frame.bindings):
        _fail("FRAME_BINDING_ROLE_UNKNOWN")
    for role in schema.roles:
        members = tuple(
            binding for binding in frame.bindings
            if binding.role_id == role.role_id)
        if not role.min_cardinality <= len(members) <= role.max_cardinality:
            _fail("FRAME_ROLE_CARDINALITY_INVALID")
        if tuple(item.occurrence_index for item in members) != tuple(
                range(len(members))):
            _fail("FRAME_ROLE_OCCURRENCE_SEQUENCE_INVALID")
        for member in members:
            if member.child_frame is not None:
                if not set(member.child_frame.type_ids).intersection(
                        role.allowed_type_ids):
                    _fail("FRAME_ROLE_TYPE_INVALID")
            concepts = ((member.concept,) if member.concept is not None
                        else member.alternatives)
            if any(not set(concept.type_ids).intersection(role.allowed_type_ids)
                   for concept in concepts):
                _fail("FRAME_ROLE_TYPE_INVALID")
def classify_frame(
    frame: FrameInstance | AtomicFrame,
    schema: FrameSchema | None,
    schema_map: SchemaTagMap,
) -> PackDecision:
    """Select representation from typed frame properties, never exception control flow."""
    if not isinstance(schema_map, SchemaTagMap):
        _fail("FRAME_SCHEMA_TAG_MAP_REQUIRED")
    if isinstance(frame, AtomicFrame):
        if schema is not None:
            _fail("FRAME_ATOMIC_SCHEMA_FORBIDDEN")
        return PackDecision(
            PackDisposition.ATOMIC, FallbackReason.ATOMIC_FRAME, None)
    if not isinstance(frame, FrameInstance) or not isinstance(schema, FrameSchema):
        _fail("FRAME_PACK_INPUT_INVALID")
    if ((frame.frame_schema_id, frame.frame_schema_revision)
            != (schema.schema_id, schema.revision)):
        _fail("FRAME_PACK_SCHEMA_IDENTITY_MISMATCH")
    _validate_frame_schema_shape(frame, schema)
    _frame_semantic_release(frame, schema_map)
    schema_tag = schema_map.tag_for(schema)
    if schema_tag is None:
        return PackDecision(
            PackDisposition.EXTENDED,
            FallbackReason.SCHEMA_TAG_UNAVAILABLE,
            None,
        )
    if (len(schema.roles) != SLOT_COUNT
            or any(role.min_cardinality != 1 or role.max_cardinality != 1
                   for role in schema.roles)):
        return PackDecision(
            PackDisposition.EXTENDED,
            FallbackReason.SCHEMA_NOT_FOUR_SINGULAR_ROLES,
            schema_tag,
        )
    if len(frame.bindings) != SLOT_COUNT:
        return PackDecision(
            PackDisposition.EXTENDED,
            FallbackReason.SLOT_COUNT_NOT_FOUR,
            schema_tag,
        )
    role_ids = tuple(binding.role_id for binding in frame.bindings)
    if len(role_ids) != len(set(role_ids)):
        return PackDecision(
            PackDisposition.EXTENDED,
            FallbackReason.REPEATED_ROLE_OCCURRENCE,
            schema_tag,
        )
    if any(binding.child_frame is not None for binding in frame.bindings):
        return PackDecision(
            PackDisposition.EXTENDED,
            FallbackReason.CHILD_FRAME,
            schema_tag,
        )
    if any(binding.state is not BindingState.VALUE or binding.concept is None
           for binding in frame.bindings):
        return PackDecision(
            PackDisposition.EXTENDED,
            FallbackReason.NON_VALUE_BINDING,
            schema_tag,
        )
    if any(binding.concept.abi_index >= SLOT_LIMIT for binding in frame.bindings):
        return PackDecision(
            PackDisposition.EXTENDED,
            FallbackReason.INDEX_REQUIRES_UINT32,
            schema_tag,
        )
    return PackDecision(
        PackDisposition.COMPACT,
        FallbackReason.COMPACT_ELIGIBLE,
        schema_tag,
    )
