"""Source-owned frame micro behavior."""
from __future__ import annotations
from ...source_adapters.structure import inspect_source_query
from ..atlas_projection import FrozenAtlasSnapshot
from ..frame_schema import ChildFrameRef, FrameTree, RoleOccurrence, SourceSpan, bind_frame_instance, occurrence_id, validate_frame_tree
from .common import _adapter_fail, _schema_for_symbol, _source_id, _source_terminal


def _bind_source_expression(
    node: dict,
    *,
    snapshot: FrozenAtlasSnapshot,
    graph: dict,
    assignments: dict,
    adapter_id: str,
    source_instance_id: str,
    path: tuple[int, ...],
    span: SourceSpan,
    parent_occurrence_id: str | None,
    causal_prefix_end: int,
) -> tuple[FrameTree, str]:
    try:
        shape = inspect_source_query(node)
    except ValueError:
        _adapter_fail("FRAME_SOURCE_QUERY_INVALID", adapter_id, span, "<operator>")
    symbol = shape.root
    schema, signature = _schema_for_symbol(
        snapshot, graph, symbol, "source:" + str(node.get("kind")),
        adapter_id=adapter_id, span=span, scope="source-query")
    args = node.get("args")
    if not isinstance(args, list) or len(args) != len(signature.inputs):
        _adapter_fail("FRAME_SOURCE_QUERY_ARITY_INVALID",
                      adapter_id, span, "<operator>")

    current_occurrence = occurrence_id(source_instance_id, path)
    bindings = []
    children = []
    role_counts: dict[str, int] = {}
    for index, (argument, expected_type, role_spec) in enumerate(
            zip(args, signature.inputs, schema.roles)):
        role_id = role_spec.role_id
        occurrence = role_counts.get(role_id, 0)
        role_counts[role_id] = occurrence + 1
        if isinstance(argument, dict) and argument.get("kind") in {
                "compare", "relation", "apply", "op"}:
            child, child_type = _bind_source_expression(
                argument,
                snapshot=snapshot,
                graph=graph,
                assignments=assignments,
                adapter_id=adapter_id,
                source_instance_id=source_instance_id,
                path=(*path, index),
                span=span,
                parent_occurrence_id=current_occurrence,
                causal_prefix_end=causal_prefix_end,
            )
            if child_type != expected_type:
                _adapter_fail("FRAME_SOURCE_CHILD_TYPE_INVALID",
                              adapter_id, span, role_id)
            children.append(child)
            bindings.append(RoleOccurrence(
                role_id,
                occurrence,
                child_frame=ChildFrameRef(
                    child.root.occurrence_id,
                    child.root.content_digest,
                    (child_type,),
                ),
            ))
        else:
            bindings.append(RoleOccurrence(
                role_id,
                occurrence,
                concept=_source_terminal(
                    argument,
                    expected_type,
                    snapshot=snapshot,
                    graph=graph,
                    assignments=assignments,
                    adapter_id=adapter_id,
                    span=span,
                    role_id=role_id,
                ),
            ))
    frame = bind_frame_instance(
        schema,
        snapshot,
        source_instance_id=source_instance_id,
        structural_path=path,
        source_span=span,
        parent_occurrence_id=parent_occurrence_id,
        bindings=tuple(bindings),
        causal_prefix_end=causal_prefix_end,
        declared_scope="source-query",
        source_graph=graph,
        source_adapter_id=adapter_id,
    )
    tree = FrameTree(frame, tuple(children))
    return validate_frame_tree(tree), signature.output

def _bind_source_row(
    row: dict,
    snapshot: FrozenAtlasSnapshot,
    graph: dict,
    *,
    adapter_id: str,
    span: SourceSpan,
    causal_prefix_end: int,
) -> FrameTree:
    record = row.get("record")
    if not isinstance(record, dict):
        _adapter_fail("FRAME_SOURCE_RECORD_MISSING",
                      adapter_id, span, "<source-row>")
    query = record.get("query") or record.get("expression")
    if not isinstance(query, dict):
        _adapter_fail("FRAME_SOURCE_QUERY_MISSING",
                      adapter_id, span, "<source-row>")
    tree, _ = _bind_source_expression(
        query,
        snapshot=snapshot,
        graph=graph,
        assignments=record.get("assignments", {}),
        adapter_id=adapter_id,
        source_instance_id=_source_id(row, adapter_id, span),
        path=(),
        span=span,
        parent_occurrence_id=None,
        causal_prefix_end=causal_prefix_end,
    )
    return tree
