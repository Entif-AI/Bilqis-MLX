"""Occurrence-aware frame-schema instances with source-owned authority."""
from __future__ import annotations
from .. import frame_schema as _facade

from dataclasses import dataclass
import json

from .contracts import FRAME_INSTANCE_RECORD, ATOMIC_FRAME_RECORD, FRAME_TREE_RECORD, _SHA256
from .schema import SourceSpan, FrameSchema
from .roles import RoleOccurrence, FrameEdge


@dataclass(frozen=True)
class FrameInstance:
    frame_schema_id: str
    frame_schema_revision: int
    occurrence_id: str
    content_digest: str
    source_instance_id: str
    structural_path: tuple[int, ...]
    source_span: SourceSpan
    parent_occurrence_id: str | None
    bindings: tuple[RoleOccurrence, ...]
    schema_role_order: tuple[str, ...]
    causal_prefix_end: int
    schema_version: str = FRAME_INSTANCE_RECORD

    def __post_init__(self) -> None:
        keys = tuple(binding.key for binding in self.bindings)
        if (not isinstance(self.frame_schema_id, str) or not self.frame_schema_id
                or type(self.frame_schema_revision) is not int or self.frame_schema_revision < 1
                or not _SHA256.fullmatch(self.occurrence_id)
                or not _SHA256.fullmatch(self.content_digest)
                or not isinstance(self.source_instance_id, str) or not self.source_instance_id
                or any(type(item) is not int or item < 0 for item in self.structural_path)
                or (self.parent_occurrence_id is not None
                    and not _SHA256.fullmatch(self.parent_occurrence_id))
                or len(keys) != len(set(keys))
                or not isinstance(self.schema_role_order, tuple)
                or not self.schema_role_order
                or len(self.schema_role_order) != len(set(self.schema_role_order))
                or any(not isinstance(role, str) or not role
                       for role in self.schema_role_order)
                or any(key[0] not in self.schema_role_order for key in keys)
                or type(self.causal_prefix_end) is not int
                or self.causal_prefix_end < self.source_span.end
                or self.schema_version != FRAME_INSTANCE_RECORD):
            _facade._fail("FRAME_INSTANCE_INVALID")
        rank = {role: index for index, role in enumerate(self.schema_role_order)}
        if keys != tuple(sorted(
                keys, key=lambda key: (rank[key[0]], key[1]))):
            _facade._fail("FRAME_BINDING_ORDER_NONCANONICAL")
        if self.occurrence_id != _facade._occurrence_digest(
                self.source_instance_id, self.structural_path):
            _facade._fail("FRAME_OCCURRENCE_ID_MISMATCH")
        if self.content_digest != _facade._frame_content_digest(
                self.frame_schema_id, self.frame_schema_revision,
                self.schema_role_order, self.bindings):
            _facade._fail("FRAME_CONTENT_DIGEST_MISMATCH")

    @property
    def child_edges(self) -> tuple[FrameEdge, ...]:
        return tuple(
            FrameEdge(
                self.occurrence_id,
                binding.role_id,
                binding.occurrence_index,
                binding.child_frame.occurrence_id,
            )
            for binding in self.bindings
            if binding.child_frame is not None
        )

    def canonical_bytes(self) -> bytes:
        return _facade._bytes(_facade.asdict(self))



@dataclass(frozen=True)
class AtomicFrame:
    occurrence_id: str
    content_digest: str
    source_instance_id: str
    structural_path: tuple[int, ...]
    source_span: SourceSpan
    parent_occurrence_id: str | None
    ast_construct: str
    source_payload: str
    causal_prefix_end: int
    schema_version: str = ATOMIC_FRAME_RECORD

    def __post_init__(self) -> None:
        try:
            json.loads(self.source_payload)
        except (TypeError, ValueError):
            _facade._fail("FRAME_ATOMIC_SOURCE_PAYLOAD_INVALID")
        if (not _SHA256.fullmatch(self.occurrence_id)
                or not _SHA256.fullmatch(self.content_digest)
                or not self.source_instance_id
                or any(type(item) is not int or item < 0 for item in self.structural_path)
                or (self.parent_occurrence_id is not None
                    and not _SHA256.fullmatch(self.parent_occurrence_id))
                or not self.ast_construct
                or type(self.causal_prefix_end) is not int
                or self.causal_prefix_end < self.source_span.end
                or self.schema_version != ATOMIC_FRAME_RECORD):
            _facade._fail("FRAME_ATOMIC_FALLBACK_INVALID")

    @property
    def source_data(self):
        return json.loads(self.source_payload)



@dataclass(frozen=True)
class FrameTree:
    root: FrameInstance | AtomicFrame
    children: tuple["FrameTree", ...] = ()
    schema_version: str = FRAME_TREE_RECORD

    def __post_init__(self) -> None:
        if self.schema_version != FRAME_TREE_RECORD:
            _facade._fail("FRAME_TREE_INVALID")



def occurrence_id(source_instance_id: str, structural_path: tuple[int, ...]) -> str:
    _facade._text(source_instance_id, "FRAME_SOURCE_INSTANCE_ID_INVALID")
    if any(type(item) is not int or item < 0 for item in structural_path):
        _facade._fail("FRAME_STRUCTURAL_PATH_INVALID")
    return _facade._occurrence_digest(source_instance_id, structural_path)



def content_digest(
    schema: FrameSchema,
    bindings: tuple[RoleOccurrence, ...],
) -> str:
    return _facade._frame_content_digest(
        schema.schema_id, schema.revision,
        tuple(role.role_id for role in schema.roles), bindings)



def make_frame_instance(
    schema: FrameSchema,
    *,
    source_instance_id: str,
    structural_path: tuple[int, ...],
    source_span: SourceSpan,
    parent_occurrence_id: str | None,
    bindings: tuple[RoleOccurrence, ...],
    causal_prefix_end: int,
) -> FrameInstance:
    role_ids = {role.role_id for role in schema.roles}
    if any(binding.role_id not in role_ids for binding in bindings):
        _facade._fail("FRAME_BINDING_ROLE_UNKNOWN")
    rank = {role.role_id: index for index, role in enumerate(schema.roles)}
    ordered = tuple(sorted(
        bindings, key=lambda item: (rank[item.role_id], item.occurrence_index)))
    return FrameInstance(
        frame_schema_id=schema.schema_id,
        frame_schema_revision=schema.revision,
        occurrence_id=_facade.occurrence_id(source_instance_id, structural_path),
        content_digest=_facade.content_digest(schema, ordered),
        source_instance_id=source_instance_id,
        structural_path=structural_path,
        source_span=source_span,
        parent_occurrence_id=parent_occurrence_id,
        bindings=ordered,
        schema_role_order=tuple(role.role_id for role in schema.roles),
        causal_prefix_end=causal_prefix_end,
    )
