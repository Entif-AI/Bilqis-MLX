"""Positions for causal source-prefix compilation."""
from __future__ import annotations
from .. import frame_compiler as _facade
from dataclasses import dataclass
from enum import Enum

from ..frame_codec import PackedFrame, SchemaTagMap
from .contracts import COMPILED_POSITION_SCHEMA, COMPILED_BATCH_SCHEMA
from .source import SourceAtom


class PositionKind(str, Enum):
    ATOM = "ATOM"
    CLOSURE = "CLOSURE"



@dataclass(frozen=True)
class CompiledPosition:
    source_index: int
    kind: PositionKind
    atom: SourceAtom | None = None
    packed: PackedFrame | None = None
    frame_handle: str | None = None
    schema_version: str = COMPILED_POSITION_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.source_index) is not int or self.source_index < 0
                or not isinstance(self.kind, PositionKind)
                or ((self.kind is PositionKind.ATOM)
                    != (self.atom is not None))
                or ((self.kind is PositionKind.CLOSURE)
                    != (self.packed is not None))
                or ((self.kind is PositionKind.CLOSURE)
                    != (self.frame_handle is not None))
                or (self.atom is not None
                    and (not isinstance(self.atom, SourceAtom)
                         or self.atom.index != self.source_index))
                or (self.packed is not None
                    and not isinstance(self.packed, PackedFrame))
                or (self.frame_handle is not None
                    and (not isinstance(self.frame_handle, str)
                         or not self.frame_handle))
                or self.schema_version != COMPILED_POSITION_SCHEMA):
            _facade._invalid("BAMF_PREFIX_POSITION_INVALID")

    @property
    def cache_identity(self) -> tuple:
        if self.kind is PositionKind.ATOM:
            return (self.source_index, "ATOM", self.atom.token,
                    self.atom.source_reference)
        return (self.source_index, "CLOSURE", self.frame_handle,
                self.packed.projection_sha256, self.packed.sidecar.digest)



def _prefix_digest(
    source_id: str, release: str, visible_end: int,
    schema_map: SchemaTagMap, context_digest: str | None,
    positions: tuple[CompiledPosition, ...],
    scope: str, policy_version: tuple[str, int, int, int],
) -> str:
    return _facade.contract_digest((
        COMPILED_BATCH_SCHEMA, source_id, release, visible_end,
        schema_map.digest, context_digest, scope, policy_version,
        tuple(item.cache_identity for item in positions),
    ))



def _canonical_position_order(
    positions: tuple[CompiledPosition, ...], visible_end: int,
) -> bool:
    next_atom = 0
    last_source = -1
    for position in positions:
        if position.source_index < last_source:
            return False
        if position.kind is PositionKind.ATOM:
            if position.source_index != next_atom:
                return False
            next_atom += 1
        elif position.source_index >= next_atom:
            return False
        last_source = position.source_index
    return next_atom == visible_end
