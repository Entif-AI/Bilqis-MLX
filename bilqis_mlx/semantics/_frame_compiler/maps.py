"""Maps for causal source-prefix compilation."""
from __future__ import annotations
from .._public_identity.facade_dependency import public_facade as _public_facade

def _public():
    return _public_facade("bilqis_mlx.semantics.frame_compiler")
from dataclasses import dataclass
from ..frame_schema import SourceSpan
from .contracts import _invalid, PREFIX_MAPS_SCHEMA, _SHA
from .positions import PositionKind


@dataclass(frozen=True)
class SourcePosition:
    position_index: int
    source_span: SourceSpan
    kind: PositionKind
    source_reference: str

    def __post_init__(self) -> None:
        if (type(self.position_index) is not int
                or self.position_index < 0
                or not isinstance(self.source_span, SourceSpan)
                or not isinstance(self.kind, PositionKind)
                or not isinstance(self.source_reference, str)
                or not self.source_reference):
            _public()._invalid("BAMF_PREFIX_SOURCE_POSITION_INVALID")



@dataclass(frozen=True)
class ScopeBoundary:
    scope: str
    start_position: int
    end_position: int
    frame_handle: str | None

    def __post_init__(self) -> None:
        if (not isinstance(self.scope, str) or not self.scope
                or type(self.start_position) is not int
                or type(self.end_position) is not int
                or not 0 <= self.start_position <= self.end_position
                or (self.frame_handle is not None
                    and (not isinstance(self.frame_handle, str)
                         or not self.frame_handle))):
            _public()._invalid("BAMF_PREFIX_SCOPE_BOUNDARY_INVALID")



@dataclass(frozen=True)
class RoleAccess:
    frame_handle: str
    position_index: int
    role_id: str
    occurrence_index: int
    state: str
    semantic_ids: tuple[str, ...]
    abi_indices: tuple[int, ...]
    source_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if (not isinstance(self.frame_handle, str)
                or not self.frame_handle
                or type(self.position_index) is not int
                or self.position_index < 0
                or not isinstance(self.role_id, str) or not self.role_id
                or type(self.occurrence_index) is not int
                or self.occurrence_index < 0
                or not isinstance(self.state, str) or not self.state
                or not isinstance(self.semantic_ids, tuple)
                or not isinstance(self.abi_indices, tuple)
                or not isinstance(self.source_references, tuple)
                or not (len(self.semantic_ids) == len(self.abi_indices)
                        == len(self.source_references))):
            _public()._invalid("BAMF_PREFIX_ROLE_ACCESS_INVALID")



@dataclass(frozen=True)
class ExpansionHandle:
    frame_handle: str
    position_index: int
    occurrence_id: str
    content_digest: str
    projection_digest: str
    source_span: SourceSpan

    def __post_init__(self) -> None:
        if (not isinstance(self.frame_handle, str)
                or not self.frame_handle
                or type(self.position_index) is not int
                or self.position_index < 0
                or any(not isinstance(item, str)
                       or not _SHA.fullmatch(item)
                       for item in (
                           self.occurrence_id, self.content_digest,
                           self.projection_digest))
                or not isinstance(self.source_span, SourceSpan)):
            _public()._invalid("BAMF_PREFIX_EXPANSION_HANDLE_INVALID")



@dataclass(frozen=True)
class PrefixMaps:
    position_to_source: tuple[SourcePosition, ...]
    source_to_positions: tuple[tuple[int, ...], ...]
    prefix_ends: tuple[int, ...]
    scope_boundaries: tuple[ScopeBoundary, ...]
    padding_mask: tuple[bool, ...]
    role_access: tuple[RoleAccess, ...]
    expansion_handles: tuple[ExpansionHandle, ...]
    schema_version: str = PREFIX_MAPS_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.position_to_source, tuple)
                or any(not isinstance(item, SourcePosition)
                       for item in self.position_to_source)
                or not isinstance(self.source_to_positions, tuple)
                or any(not isinstance(row, tuple)
                       or any(type(index) is not int or index < 0
                              for index in row)
                       for row in self.source_to_positions)
                or not isinstance(self.prefix_ends, tuple)
                or any(type(index) is not int or index < 0
                       for index in self.prefix_ends)
                or not isinstance(self.scope_boundaries, tuple)
                or any(not isinstance(item, ScopeBoundary)
                       for item in self.scope_boundaries)
                or not isinstance(self.padding_mask, tuple)
                or any(type(item) is not bool
                       for item in self.padding_mask)
                or len(self.padding_mask) != len(self.position_to_source)
                or not isinstance(self.role_access, tuple)
                or any(not isinstance(item, RoleAccess)
                       for item in self.role_access)
                or not isinstance(self.expansion_handles, tuple)
                or any(not isinstance(item, ExpansionHandle)
                       for item in self.expansion_handles)
                or self.schema_version != PREFIX_MAPS_SCHEMA):
            _public()._invalid("BAMF_PREFIX_MAPS_INVALID")
