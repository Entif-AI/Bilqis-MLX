"""Dependency order and source-visible DAG value resolution."""
from __future__ import annotations

from .._frame_schema.instances import FrameInstance
from .._frame_schema.roles import BindingState
from ..cognitive_operators.registry import OperatorBinding
from ..cognitive_operators.types import TypedValue, ValueState
from .contracts import DAGBudget, DAGNode, DAGOperand, DAGProgram, RefKind, _invalid

def _topological(
    program: DAGProgram, budget: DAGBudget,
) -> tuple[DAGNode, ...]:
    if len(program.nodes) > budget.max_nodes:
        _invalid("BAMF_DAG_NODE_BUDGET_EXCEEDED")
    by_id = {node.node_id: node for node in program.nodes}
    visiting: set[str] = set()
    visited: set[str] = set()
    depth: dict[str, int] = {}
    order: list[DAGNode] = []

    def visit(node_id: str) -> int:
        if node_id in visiting:
            _invalid("BAMF_DAG_CYCLE")
        if node_id in visited:
            return depth[node_id]
        node = by_id.get(node_id)
        if node is None:
            _invalid("BAMF_DAG_RESULT_REFERENCE_MISSING")
        visiting.add(node_id)
        parents = []
        refs = (
            tuple(ref for ref in node.operands if ref is not None)
            + tuple(ref for group in node.candidate_operand_refs for ref in group)
        )
        for operand in refs:
            if operand.kind is RefKind.RESULT:
                parents.append(visit(operand.result_node_id))
        node_depth = 1 + max(parents, default=0)
        if node_depth > budget.max_depth:
            _invalid("BAMF_DAG_DEPTH_BUDGET_EXCEEDED")
        depth[node_id] = node_depth
        visiting.remove(node_id)
        visited.add(node_id)
        order.append(node)
        return node_depth

    visit(program.output_node_id)
    if len(visited) != len(program.nodes):
        _invalid("BAMF_DAG_ORPHAN_NODES")
    return tuple(order)


def _visible_source(
    ref: DAGOperand,
    binding: OperatorBinding,
    approved: dict,
) -> TypedValue | None:
    if ref.kind is RefKind.LITERAL:
        match = next((
            operand.typed for operand in binding.operands
            if operand.typed.source_handle == ref.source_handle
        ), None)
        if match is None or match.type_name != ref.type_name:
            _invalid("BAMF_DAG_LITERAL_NOT_SOURCE_VISIBLE")
        return match
    if ref.kind is RefKind.RESULT:
        return None
    envelope = approved.get(ref.frame_handle)
    if envelope is None or not isinstance(envelope.frame, FrameInstance):
        _invalid("BAMF_DAG_FRAME_NOT_APPROVED")
    if envelope.frame.occurrence_id != ref.frame_occurrence_id:
        _invalid("BAMF_DAG_FRAME_OCCURRENCE_DRIFT")
    member = next((
        item for item in envelope.members
        if (item.role_id, item.occurrence_index)
        == (ref.role_id, ref.occurrence_index)
    ), None)
    occurrence = next((
        item for item in envelope.frame.bindings
        if item.key == (ref.role_id, ref.occurrence_index)
    ), None)
    if member is None or occurrence is None:
        _invalid("BAMF_DAG_ROLE_NOT_SOURCE_VISIBLE")
    if occurrence.state is not BindingState.VALUE:
        state = (
            ValueState.NONE if occurrence.state is BindingState.NONE
            else ValueState.UNKNOWN if occurrence.state is BindingState.UNKNOWN
            else ValueState.UNRESOLVED
        )
        return TypedValue(
            "ConceptRef", None, binding.task.semantic_release,
            source_handle=member.source_handle, state=state)
    if occurrence.concept is None:
        _invalid("BAMF_DAG_SOURCE_CONCEPT_MISSING")
    return TypedValue(
        "ConceptRef", occurrence.concept, binding.task.semantic_release,
        source_handle=member.source_handle)

