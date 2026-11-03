"""Visibility for causal source-prefix compilation."""
from __future__ import annotations
from .._public_identity.facade_dependency import public_facade as _public_facade

def _public():
    return _public_facade("bilqis_mlx.semantics.frame_compiler")
from dataclasses import dataclass
from ..frame_schema import AtomicFrame, FrameInstance, FrameTree, validate_frame_tree
from .contracts import _invalid, VISIBLE_AST_SCHEMA
from .source import SourceAtom, StreamingAST


@dataclass(frozen=True)
class VisibleAST:
    source_instance_id: str
    visible_end: int
    atoms: tuple[SourceAtom, ...]
    frames: tuple[FrameTree, ...]
    schema_version: str = VISIBLE_AST_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.source_instance_id, str)
                or not self.source_instance_id
                or type(self.visible_end) is not int
                or self.visible_end < 0
                or not isinstance(self.atoms, tuple)
                or tuple(atom.index for atom in self.atoms
                         if isinstance(atom, SourceAtom))
                != tuple(range(self.visible_end))
                or not isinstance(self.frames, tuple)
                or any(not isinstance(tree, FrameTree)
                       for tree in self.frames)
                or self.schema_version != VISIBLE_AST_SCHEMA):
            _public()._invalid("BAMF_PREFIX_VISIBLE_AST_INVALID")



def _closure_end(
    frame: FrameInstance | AtomicFrame, approved_by_occurrence: dict,
) -> int:
    envelope = approved_by_occurrence.get(frame.occurrence_id)
    if envelope is None:
        return frame.causal_prefix_end
    return max(
        frame.causal_prefix_end, envelope.causal_prefix_end,
        *(member.visible_at_prefix for member in envelope.members))



def _source_frames(
    ast: StreamingAST, visible_end: int, approved_by_occurrence: dict,
) -> tuple[FrameInstance | AtomicFrame, ...]:
    ordered = []
    seen = set()

    def walk(tree: FrameTree) -> None:
        for child in sorted(
                tree.children,
                key=lambda item: (
                    item.root.source_span.start,
                    item.root.source_span.end,
                    item.root.occurrence_id)):
            walk(child)
        frame = tree.root
        if _public()._closure_end(frame, approved_by_occurrence) > visible_end:
            return
        if any(_public()._closure_end(child.root, approved_by_occurrence) > visible_end
               for child in tree.children):
            _public()._invalid("BAMF_PREFIX_CHILD_FUTURE")
        # Future parent structure is never inspected or validated at p.
        _public().validate_frame_tree(tree)
        if (frame.occurrence_id in seen
                or frame.source_instance_id != ast.source_instance_id
                or frame.causal_prefix_end > len(ast.atoms)
                or frame.causal_prefix_end == 0
                or frame.source_span.end > frame.causal_prefix_end):
            _public()._invalid("BAMF_PREFIX_FRAME_SOURCE_INVALID")
        seen.add(frame.occurrence_id)
        ordered.append(frame)

    for tree in sorted(
            ast.frames,
            key=lambda item: (
                item.root.source_span.start,
                item.root.source_span.end,
                item.root.occurrence_id)):
        if (_public()._closure_end(tree.root, approved_by_occurrence) <= visible_end
                and tree.root.parent_occurrence_id is not None):
            _public()._invalid("BAMF_PREFIX_ROOT_PARENT_INVALID")
        walk(tree)
    return tuple(ordered)
