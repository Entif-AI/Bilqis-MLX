"""Occurrence-aware frame-schema bindings with source-owned authority."""
from __future__ import annotations
from .. import frame_schema as _facade

from ..atlas_projection import FrozenAtlasSnapshot

from .schema import SourceSpan, FrameSchema
from .roles import RoleOccurrence
from .instances import FrameInstance




def validate_frame_bindings(
    schema: FrameSchema,
    snapshot: FrozenAtlasSnapshot,
    *,
    bindings: tuple[RoleOccurrence, ...],
    source_span: SourceSpan,
    causal_prefix_end: int,
    declared_scope: str,
    source_graph: dict | None = None,
    source_adapter_id: str | None = None,
) -> tuple[RoleOccurrence, ...]:
    if not isinstance(snapshot, FrozenAtlasSnapshot):
        _facade._fail("FRAME_ATLAS_SNAPSHOT_REQUIRED")
    if declared_scope != schema.scope:
        _facade._binding_fail("FRAME_SCOPE_MISMATCH", source_span, "<frame>")
    if type(causal_prefix_end) is not int or causal_prefix_end < source_span.end:
        _facade._binding_fail("FRAME_CAUSAL_PREFIX_INVALID", source_span, "<frame>")

    role_by_id = {role.role_id: role for role in schema.roles}
    if any(binding.role_id not in role_by_id for binding in bindings):
        unknown = next(binding.role_id for binding in bindings
                       if binding.role_id not in role_by_id)
        _facade._binding_fail("FRAME_BINDING_ROLE_UNKNOWN", source_span, unknown)
    grouped = {
        role.role_id: tuple(
            binding for binding in bindings if binding.role_id == role.role_id)
        for role in schema.roles
    }
    for role in schema.roles:
        members = grouped[role.role_id]
        if not role.min_cardinality <= len(members) <= role.max_cardinality:
            _facade._binding_fail("FRAME_ROLE_CARDINALITY_INVALID", source_span, role.role_id)
        if tuple(item.occurrence_index for item in members) != tuple(range(len(members))):
            _facade._binding_fail("FRAME_ROLE_OCCURRENCE_SEQUENCE_INVALID",
                          source_span, role.role_id)
        for member in members:
            if member.child_frame is not None:
                if not set(member.child_frame.type_ids).intersection(role.allowed_type_ids):
                    _facade._binding_fail("FRAME_ROLE_TYPE_INVALID", source_span, role.role_id)
                continue
            for concept in _facade._binding_concepts(member):
                if concept.semantic_release != snapshot.release_sha256:
                    _facade._binding_fail("FRAME_SEMANTIC_RELEASE_MISMATCH",
                                  source_span, role.role_id)
                abi = snapshot.abi_for_semantic(concept.semantic_id)
                if abi.index != concept.abi_index:
                    _facade._binding_fail("FRAME_ABI_INDEX_MISMATCH", source_span, role.role_id)
                authoritative = next(
                    (item.concept.types for item in snapshot.concepts
                     if item.concept.semantic_id == concept.semantic_id),
                    None,
                )
                if authoritative is None:
                    authoritative = _facade._formal_source_types(
                        snapshot, concept, source_graph, source_adapter_id,
                        source_span, role.role_id)
                if tuple(concept.type_ids) != tuple(authoritative):
                    _facade._binding_fail("FRAME_CONCEPT_TYPE_AUTHORITY_MISMATCH",
                                  source_span, role.role_id)
                if not set(concept.type_ids).intersection(role.allowed_type_ids):
                    _facade._binding_fail("FRAME_ROLE_TYPE_INVALID", source_span, role.role_id)

    rank = {role.role_id: index for index, role in enumerate(schema.roles)}
    return tuple(sorted(
        bindings,
        key=lambda item: (rank[item.role_id], item.occurrence_index),
    ))



def bind_frame_instance(
    schema: FrameSchema,
    snapshot: FrozenAtlasSnapshot,
    *,
    source_instance_id: str,
    structural_path: tuple[int, ...],
    source_span: SourceSpan,
    parent_occurrence_id: str | None,
    bindings: tuple[RoleOccurrence, ...],
    causal_prefix_end: int,
    declared_scope: str,
    source_graph: dict | None = None,
    source_adapter_id: str | None = None,
) -> FrameInstance:
    ordered = _facade.validate_frame_bindings(
        schema,
        snapshot,
        bindings=bindings,
        source_span=source_span,
        causal_prefix_end=causal_prefix_end,
        declared_scope=declared_scope,
        source_graph=source_graph,
        source_adapter_id=source_adapter_id,
    )
    return _facade.make_frame_instance(
        schema,
        source_instance_id=source_instance_id,
        structural_path=structural_path,
        source_span=source_span,
        parent_occurrence_id=parent_occurrence_id,
        bindings=ordered,
        causal_prefix_end=causal_prefix_end,
    )
