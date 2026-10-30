"""Source-owned frame numeric behavior."""
from __future__ import annotations
from ...generated_assessment import digest
from ...source_adapters.numeric import decode as decode_numeric
from ..atlas_projection import FrozenAtlasSnapshot
from ..core import Apply, Literal
from ..frame_schema import ChildFrameRef, ConceptRef, FrameTree, RoleOccurrence, SourceSpan, ast_construct_id, atomic_fallback, bind_frame_instance, occurrence_id, validate_frame_tree
from .common import _APPEND_ONLY_NUMERIC_NODES, _adapter_fail, _concept_ref, _schema_for_symbol, _source_id


def _numeric_literal_tree(
    value: Literal,
    *,
    snapshot: FrozenAtlasSnapshot,
    graph: dict,
    adapter_id: str,
    source_instance_id: str,
    path: tuple[int, ...],
    span: SourceSpan,
    parent_occurrence_id: str,
    causal_prefix_end: int,
) -> tuple[ConceptRef | None, FrameTree | None]:
    if value.type_name == "Number":
        return _concept_ref(
            snapshot, graph, "school.number." + value.value, "Number",
            adapter_id=adapter_id, span=span, role_id="<literal>"), None
    atomic = atomic_fallback(
        value,
        source_instance_id=source_instance_id,
        structural_path=path,
        source_span=span,
        parent_occurrence_id=parent_occurrence_id,
        causal_prefix_end=causal_prefix_end,
    )
    return None, FrameTree(atomic)

def _numeric_schema(expression, snapshot, graph, adapter_id, span):
    native_contract_owner = (
        expression.operator.symbol in _APPEND_ONLY_NUMERIC_NODES)
    schema, graph_signature = _schema_for_symbol(
        snapshot, graph, expression.operator.symbol, ast_construct_id(expression),
        adapter_id=adapter_id, span=span, scope="formal-expression",
        contract_sha256=(
            expression.operator.contract_sha256 if native_contract_owner else None))
    symbol = expression.operator.symbol
    graph_node = graph["nodes"][graph["tokens"].index(symbol)]
    if digest(graph_node) != graph["row_contract_sha256"][symbol]:
        _adapter_fail("FRAME_NUMERIC_CONTRACT_DRIFT",
                      adapter_id, span, "<operator>")
    if native_contract_owner:
        declared = _APPEND_ONLY_NUMERIC_NODES[symbol]
        if any(graph_node.get(field) != declared[field]
               for field in ("id", "semantic_id", "signature", "arity", "meaning")):
            _adapter_fail("FRAME_NUMERIC_APPEND_ONLY_NODE_DRIFT",
                          adapter_id, span, "<operator>")
    if graph_signature != expression.operator.signature:
        _adapter_fail("FRAME_NUMERIC_SIGNATURE_DRIFT",
                      adapter_id, span, "<operator>")
    if expression.operator.token_index != graph["tokens"].index(expression.operator.symbol):
        _adapter_fail("FRAME_NUMERIC_OPERATOR_INDEX_DRIFT",
                      adapter_id, span, "<operator>")
    if expression.operator.contract_sha256 != schema.ast_contract_sha256:
        _adapter_fail("FRAME_NUMERIC_CONTRACT_DRIFT",
                      adapter_id, span, "<operator>")
    return schema

def _bind_numeric_expression(
    expression: Apply,
    *,
    snapshot: FrozenAtlasSnapshot,
    graph: dict,
    adapter_id: str,
    source_instance_id: str,
    path: tuple[int, ...],
    span: SourceSpan,
    parent_occurrence_id: str | None,
    causal_prefix_end: int,
) -> tuple[FrameTree, str]:
    schema = _numeric_schema(expression, snapshot, graph, adapter_id, span)

    current_occurrence = occurrence_id(source_instance_id, path)
    bindings = []
    children = []
    for index, (argument, expected_type, role_spec) in enumerate(
            zip(expression.arguments, expression.operator.signature.inputs, schema.roles)):
        role_id = role_spec.role_id
        if isinstance(argument, Apply):
            child, child_type = _bind_numeric_expression(
                argument,
                snapshot=snapshot,
                graph=graph,
                adapter_id=adapter_id,
                source_instance_id=source_instance_id,
                path=(*path, index),
                span=span,
                parent_occurrence_id=current_occurrence,
                causal_prefix_end=causal_prefix_end,
            )
            concept = None
        else:
            concept, child = _numeric_literal_tree(
                argument,
                snapshot=snapshot,
                graph=graph,
                adapter_id=adapter_id,
                source_instance_id=source_instance_id,
                path=(*path, index),
                span=span,
                parent_occurrence_id=current_occurrence,
                causal_prefix_end=causal_prefix_end,
            )
            child_type = argument.type_name
        if child_type != expected_type:
            _adapter_fail("FRAME_NUMERIC_CHILD_TYPE_INVALID",
                          adapter_id, span, role_id)
        if child is None:
            bindings.append(RoleOccurrence(role_id, 0, concept=concept))
        else:
            children.append(child)
            bindings.append(RoleOccurrence(
                role_id,
                0,
                child_frame=ChildFrameRef(
                    child.root.occurrence_id,
                    child.root.content_digest,
                    (child_type,),
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
        declared_scope="formal-expression",
        source_graph=graph,
        source_adapter_id=adapter_id,
    )
    tree = FrameTree(frame, tuple(children))
    return validate_frame_tree(tree), expression.type_name

def _bind_numeric_row(
    row: dict,
    snapshot: FrozenAtlasSnapshot,
    graph: dict,
    *,
    adapter_id: str,
    span: SourceSpan,
    causal_prefix_end: int,
) -> FrameTree:
    record = row.get("record")
    try:
        expression = decode_numeric(record["symbols"])
    except (KeyError, TypeError, ValueError, IndexError):
        _adapter_fail("FRAME_NUMERIC_SOURCE_RECORD_INVALID",
                      adapter_id, span, "<source-row>")
    if isinstance(expression, Literal):
        atomic = atomic_fallback(
            expression,
            source_instance_id=_source_id(row, adapter_id, span),
            structural_path=(),
            source_span=span,
            parent_occurrence_id=None,
            causal_prefix_end=causal_prefix_end,
        )
        return validate_frame_tree(FrameTree(atomic))
    tree, _ = _bind_numeric_expression(
        expression,
        snapshot=snapshot,
        graph=graph,
        adapter_id=adapter_id,
        source_instance_id=_source_id(row, adapter_id, span),
        path=(),
        span=span,
        parent_occurrence_id=None,
        causal_prefix_end=causal_prefix_end,
    )
    return tree
