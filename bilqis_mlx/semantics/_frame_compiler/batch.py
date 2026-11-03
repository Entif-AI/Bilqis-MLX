"""Batch for causal source-prefix compilation."""
from __future__ import annotations
from .. import frame_compiler as _facade
from dataclasses import dataclass
from .maps import PrefixMaps
from .stats import CompileStats
from ..frame_codec import SchemaTagMap
from .contracts import COMPILED_BATCH_SCHEMA, MAX_NEURAL_POSITIONS, POLICY_VERSION_ARITY, _SHA
from .positions import PositionKind, CompiledPosition


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
                or not _facade._canonical_position_order(
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
                or self.cache_key != _facade._prefix_digest(
                    self.source_instance_id, self.semantic_release,
                    self.visible_end, self.schema_map,
                    self.context_digest, self.positions,
                    self.scope, self.policy_version)
                or self.schema_version != COMPILED_BATCH_SCHEMA):
            _facade._invalid("BAMF_PREFIX_BATCH_INVALID")

    @property
    def maps(self) -> "PrefixMaps":

        return _facade._derive_maps(self)

    @property
    def stats(self) -> "CompileStats":

        return _facade._compile_stats(self)
