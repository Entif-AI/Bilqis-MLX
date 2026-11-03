"""Bidirectional source-map derivation."""
from __future__ import annotations
from .. import frame_compiler as _facade
from ..frame_schema import SourceSpan

from .positions import PositionKind
from .batch import CompiledFrameBatch
from .maps import (
    SourcePosition, ScopeBoundary, RoleAccess, ExpansionHandle, PrefixMaps,
)


def _derive_maps(compiled: CompiledFrameBatch) -> PrefixMaps:
    source_positions = []
    source_to_positions = [
        set() for _ in range(compiled.visible_end)]
    prefix_ends = [0] * (compiled.visible_end + 1)
    role_access = []
    expansion_handles = []
    boundaries = [ScopeBoundary(
        compiled.scope, 0, len(compiled.positions), None)]
    atom_positions = {}
    for position_index, position in enumerate(compiled.positions):
        source_index = position.source_index
        prefix_ends[source_index + 1] += 1
        if position.kind is PositionKind.ATOM:
            source_positions.append(SourcePosition(
                position_index, SourceSpan(source_index, source_index + 1),
                PositionKind.ATOM, position.atom.source_reference))
            source_to_positions[source_index].add(position_index)
            atom_positions[source_index] = position_index
            continue
        sidecar = position.packed.sidecar
        source_positions.append(SourcePosition(
            position_index, sidecar.source_span,
            PositionKind.CLOSURE, position.frame_handle))
        for index in range(
                sidecar.source_span.start,
                min(sidecar.source_span.end, compiled.visible_end)):
            source_to_positions[index].add(position_index)
        source_to_positions[source_index].add(position_index)
        expansion_handles.append(ExpansionHandle(
            position.frame_handle, position_index,
            sidecar.occurrence_id, sidecar.content_digest,
            position.packed.projection_sha256, sidecar.source_span))
        start = atom_positions.get(sidecar.source_span.start)
        if start is None:
            _facade._invalid("BAMF_PREFIX_SCOPE_SOURCE_MISSING")
        boundaries.append(ScopeBoundary(
            sidecar.scope or compiled.scope,
            start, position_index + 1, position.frame_handle))
        for member in sidecar.constituents:
            role_access.append(RoleAccess(
                position.frame_handle, position_index,
                member.role_id, member.occurrence_index,
                member.state, member.semantic_ids,
                member.abi_indices, member.source_references))
    for index in range(1, len(prefix_ends)):
        prefix_ends[index] += prefix_ends[index - 1]
    return PrefixMaps(
        tuple(source_positions),
        tuple(tuple(sorted(indices)) for indices in source_to_positions),
        tuple(prefix_ends), tuple(boundaries),
        (True,) * len(compiled.positions),
        tuple(role_access), tuple(expansion_handles))
