"""Source for source-owned partial forests."""
from __future__ import annotations
from .. import partial_visible_forest as _facade
from ..frame_compiler import StreamingAST
from ..frame_schema import AtomicFrame, FrameInstance, FrameTree


def _source_tree_index(
    ast: StreamingAST,
) -> tuple[
    dict[str, FrameInstance | AtomicFrame],
    dict[str, str | None],
]:
    frames: dict[str, FrameInstance | AtomicFrame] = {}
    parents: dict[str, str | None] = {}

    def walk(tree: FrameTree, parent_occurrence_id: str | None) -> None:
        _facade.validate_frame_tree(tree)
        frame = tree.root
        if frame.occurrence_id in frames:
            _facade._invalid("BAMF_PREFIX_PARTIAL_SOURCE_DUPLICATE")
        frames[frame.occurrence_id] = frame
        parents[frame.occurrence_id] = parent_occurrence_id
        for child in tree.children:
            walk(child, frame.occurrence_id)

    for tree in ast.frames:
        walk(tree, None)
    return frames, parents



def _visible_forest_frames(
    forest: tuple[FrameTree, ...],
) -> tuple[FrameInstance | AtomicFrame, ...]:
    frames = []

    def walk(tree: FrameTree) -> None:
        frames.append(tree.root)
        for child in tree.children:
            walk(child)

    for tree in forest:
        walk(tree)
    return tuple(frames)
