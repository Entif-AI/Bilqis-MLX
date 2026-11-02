"""Compiled positions, batch identity and accounting."""
from __future__ import annotations
from .common import (COMPILED_BATCH_SCHEMA, COMPILED_POSITION_SCHEMA, Enum, MAX_NEURAL_POSITIONS, POLICY_VERSION_ARITY, PackDisposition, PackedFrame, SchemaTagMap, _SHA, _canonical_bytes, _invalid, asdict, contract_digest, dataclass)
from .source import (SourceAtom)

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
            _invalid("BAMF_PREFIX_POSITION_INVALID")

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
    return contract_digest((
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


@dataclass(frozen=True)
class CompiledFrameBatch:
    source_instance_id: str
    semantic_release: str
    visible_end: int
    positions: tuple[CompiledPosition, ...]
    schema_map: SchemaTagMap
    context_digest: str | None
    scope: str
    policy_version: tuple[str, int, int, int]
    cache_key: str
    schema_version: str = COMPILED_BATCH_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.source_instance_id, str)
                or not self.source_instance_id
                or not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or type(self.visible_end) is not int or self.visible_end < 0
                or not isinstance(self.positions, tuple)
                or len(self.positions) > MAX_NEURAL_POSITIONS
                or any(not isinstance(item, CompiledPosition)
                       or item.source_index >= self.visible_end
                       for item in self.positions)
                or not _canonical_position_order(
                    self.positions, self.visible_end)
                or (self.context_digest is None
                    and any(item.kind is PositionKind.CLOSURE
                            for item in self.positions))
                or not isinstance(self.schema_map, SchemaTagMap)
                or self.schema_map.semantic_release != self.semantic_release
                or (self.context_digest is not None
                    and (not isinstance(self.context_digest, str)
                         or not _SHA.fullmatch(self.context_digest)))
                or not isinstance(self.scope, str) or not self.scope
                or not isinstance(self.policy_version, tuple)
                or len(self.policy_version) != POLICY_VERSION_ARITY
                or not isinstance(self.policy_version[0], str)
                or not self.policy_version[0]
                or any(type(epoch) is not int or epoch < 0
                       for epoch in self.policy_version[1:])
                or not isinstance(self.cache_key, str)
                or self.cache_key != _prefix_digest(
                    self.source_instance_id, self.semantic_release,
                    self.visible_end, self.schema_map,
                    self.context_digest, self.positions,
                    self.scope, self.policy_version)
                or self.schema_version != COMPILED_BATCH_SCHEMA):
            _invalid("BAMF_PREFIX_BATCH_INVALID")

    @property
    def maps(self) -> "PrefixMaps":
        from .maps import _derive_maps

        return _derive_maps(self)

    @property
    def stats(self) -> "CompileStats":
        return _compile_stats(self)


@dataclass(frozen=True)
class CompileStats:
    actual_atoms: int
    actual_frames: int
    neural_positions: int
    disposition_shares: tuple[tuple[str, int, int], ...]
    sidecar_bytes: int

    def __post_init__(self) -> None:
        if (any(type(value) is not int or value < 0
                for value in (
                    self.actual_atoms, self.actual_frames,
                    self.neural_positions, self.sidecar_bytes))
                or self.actual_atoms + self.actual_frames
                != self.neural_positions
                or not isinstance(self.disposition_shares, tuple)
                or tuple(item[0] for item in self.disposition_shares)
                != ("COMPACT", "EXTENDED", "ATOMIC")
                or any(type(count) is not int or count < 0
                       or type(total) is not int
                       or total != self.actual_frames
                       for _, count, total in self.disposition_shares)
                or sum(count for _, count, _ in self.disposition_shares)
                != self.actual_frames):
            _invalid("BAMF_PREFIX_STATS_INVALID")


def _compile_stats(compiled: CompiledFrameBatch) -> CompileStats:
    closures = tuple(
        position.packed for position in compiled.positions
        if position.kind is PositionKind.CLOSURE)
    count = len(closures)
    shares = tuple(
        (disposition.name,
         sum(packed.disposition is disposition for packed in closures),
         count)
        for disposition in (
            PackDisposition.COMPACT,
            PackDisposition.EXTENDED,
            PackDisposition.ATOMIC))
    return CompileStats(
        len(compiled.positions) - count, count,
        len(compiled.positions), shares,
        sum(len(_canonical_bytes(asdict(packed.sidecar)))
            for packed in closures))
