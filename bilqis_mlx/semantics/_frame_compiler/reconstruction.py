"""Reconstruction for causal source-prefix compilation."""
from __future__ import annotations
from ..frame_codec import unpack_frame
from ..frame_schema import AtomicFrame, FrameInstance, FrameTree, validate_frame_tree
from .batch import CompiledFrameBatch
from .contracts import _invalid
from .positions import PositionKind
from .visibility import VisibleAST


def reconstruct(compiled: CompiledFrameBatch) -> VisibleAST:
    """Reconstruct exactly the source atoms and frame forest visible at p."""
    if not isinstance(compiled, CompiledFrameBatch):
        _invalid("BAMF_PREFIX_RECONSTRUCT_INPUT_INVALID")
    compiled.__post_init__()
    if (any(item.kind is PositionKind.CLOSURE
            for item in compiled.positions)
            and compiled.context_digest is None):
        _invalid("BAMF_PREFIX_CLOSURE_AUTHORITY_MISSING")
    atoms = []
    frames = []
    seen = set()
    last_index = -1
    for position in compiled.positions:
        if position.source_index < last_index:
            _invalid("BAMF_PREFIX_POSITION_ORDER_INVALID")
        last_index = position.source_index
        if position.kind is PositionKind.ATOM:
            if position.source_index != len(atoms):
                _invalid("BAMF_PREFIX_ATOM_ORDER_INVALID")
            atoms.append(position.atom)
            continue
        if (not atoms or position.source_index != atoms[-1].index):
            _invalid("BAMF_PREFIX_CLOSURE_ORDER_INVALID")
        frame = unpack_frame(
            position.packed, schema_map=compiled.schema_map)
        if (frame.occurrence_id in seen
                or frame.source_instance_id != compiled.source_instance_id
                or frame.causal_prefix_end > position.source_index + 1):
            _invalid("BAMF_PREFIX_CLOSURE_SOURCE_INVALID")
        seen.add(frame.occurrence_id)
        frames.append(frame)
    if len(atoms) != compiled.visible_end:
        _invalid("BAMF_PREFIX_ATOM_COUNT_INVALID")

    by_id = {frame.occurrence_id: frame for frame in frames}
    closing_order = {
        frame.occurrence_id: index for index, frame in enumerate(frames)}
    for frame in frames:
        if (frame.parent_occurrence_id in by_id
                and closing_order[frame.parent_occurrence_id]
                <= closing_order[frame.occurrence_id]):
            _invalid("BAMF_PREFIX_CHILD_CLOSURE_ORDER_INVALID")

    visiting = set()
    visited = set()

    def build(frame: FrameInstance | AtomicFrame) -> FrameTree:
        if frame.occurrence_id in visiting or frame.occurrence_id in visited:
            _invalid("BAMF_PREFIX_FRAME_TREE_CYCLE")
        visiting.add(frame.occurrence_id)
        children = tuple(
            build(child) for child in frames
            if child.parent_occurrence_id == frame.occurrence_id)
        tree = FrameTree(frame, children)
        validate_frame_tree(tree)
        visiting.remove(frame.occurrence_id)
        visited.add(frame.occurrence_id)
        return tree

    roots = tuple(
        build(frame) for frame in frames
        if frame.parent_occurrence_id not in by_id)
    if len(visited) != len(frames):
        _invalid("BAMF_PREFIX_FRAME_TREE_UNREACHABLE")
    return VisibleAST(
        compiled.source_instance_id, compiled.visible_end,
        tuple(atoms), roots)
