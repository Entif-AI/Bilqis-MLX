"""Occurrence-aware frame-schema forest with source-owned authority."""
from __future__ import annotations

from ..atlas_projection import FrozenAtlasSnapshot
from ..core import Apply
from .contracts import _fail
from .schema import SourceSpan, FrameSchema
from .roles import RoleOccurrence
from .instances import AtomicFrame, FrameTree
from .errors import _binding_fail
from .ast_identity import source_ast_construct_id, atomic_fallback
from .bindings import bind_frame_instance


def bind_ast_frames(
    ast: object,
    snapshot: FrozenAtlasSnapshot,
    *,
    schema: FrameSchema | None,
    source_instance_id: str,
    structural_path: tuple[int, ...] = (),
    source_span: SourceSpan,
    parent_occurrence_id: str | None = None,
    bindings: tuple[RoleOccurrence, ...] = (),
    causal_prefix_end: int,
    declared_scope: str | None = None,
) -> FrameTree:
    """Bind one native AST node or preserve it atomically when no schema is approved."""
    if schema is None:
        return FrameTree(atomic_fallback(
            ast,
            source_instance_id=source_instance_id,
            structural_path=structural_path,
            source_span=source_span,
            parent_occurrence_id=parent_occurrence_id,
            causal_prefix_end=causal_prefix_end,
        ))
    if source_ast_construct_id(ast) != schema.ast_construct:
        _fail("FRAME_AST_CONSTRUCT_MISMATCH")
    if isinstance(ast, Apply):
        if schema.ast_contract_sha256 is None:
            _binding_fail("FRAME_AST_CONTRACT_REQUIRED",
                          source_span, "<operator>")
        if ast.operator.contract_sha256 != schema.ast_contract_sha256:
            _binding_fail("FRAME_AST_CONTRACT_MISMATCH",
                          source_span, "<operator>")
    instance = bind_frame_instance(
        schema,
        snapshot,
        source_instance_id=source_instance_id,
        structural_path=structural_path,
        source_span=source_span,
        parent_occurrence_id=parent_occurrence_id,
        bindings=bindings,
        causal_prefix_end=causal_prefix_end,
        declared_scope=declared_scope or "",
    )
    return FrameTree(instance)



def validate_frame_tree(tree: FrameTree) -> FrameTree:
    if not isinstance(tree, FrameTree):
        _fail("FRAME_TREE_INVALID")
    root = tree.root
    if isinstance(root, AtomicFrame):
        if tree.children:
            _fail("FRAME_ATOMIC_CHILDREN_FORBIDDEN")
        return tree
    expected = {
        binding.child_frame.occurrence_id: binding.child_frame
        for binding in root.bindings if binding.child_frame is not None
    }
    actual = {
        child.root.occurrence_id: child.root
        for child in tree.children
    }
    if set(expected) != set(actual):
        _binding_fail("FRAME_CHILD_OCCURRENCE_MISMATCH",
                      root.source_span, "<child-frame>")
    for occurrence, reference in expected.items():
        child = actual[occurrence]
        if child.content_digest != reference.content_digest:
            _binding_fail("FRAME_CHILD_CONTENT_MISMATCH",
                          root.source_span, "<child-frame>")
    for child in tree.children:
        validate_frame_tree(child)
    return tree
