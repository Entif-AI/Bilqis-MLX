"""Validation of canonical immutable DAG records."""
from __future__ import annotations
from .._public_identity.facade_dependency import public_facade
from ..cognitive_dag import (
    DAGOperand, DAGProgram, DAGBudget, DAGNode, TaskGoal, DAGResult, DAGReceipt,
    OperatorBinding, TypedValue, PureOperationMemo,
)


def _public():
    return public_facade("bilqis_mlx.semantics.cognitive_dag")


def validate_dagresult(self) -> None:
    if (not isinstance(self.answer, _public().TypedValue)
            or not isinstance(self.receipt, _public().DAGReceipt)
            or self.answer.semantic_release
            != self.receipt.semantic_release
            or (self.answer.state is _public().ValueState.UNRESOLVED)
            != (self.receipt.unresolved_signature is not None)
            or self.schema_version != _public().DAG_RESULT_SCHEMA):
        _public()._invalid("BAMF_DAG_RESULT_INVALID")


def validate_dagreceipt(self) -> None:
    if (not all(isinstance(item, str) and _public()._SHA.fullmatch(item) for item in (
                self.semantic_release, self.source_binding_digest))
            or not all(type(value) is int and value >= 0 for value in (
                self.operation_count, self.lookup_count,
                self.memo_hit_count))
            or self.lookup_count > _public().MAX_DAG_NODES
            or self.memo_hit_count > self.lookup_count
            or self.operation_count + self.memo_hit_count
            > self.lookup_count
            or self.lookup_count - (
                self.operation_count + self.memo_hit_count) > 1
            or not isinstance(self.selected_bindings, tuple)
            or not isinstance(self.executed_nodes, tuple)
            or any(not isinstance(item, tuple) or len(item) != 3
                   or not _public()._name(item[0]) or not _public()._name(item[1])
                   or not isinstance(item[2], tuple)
                   or any(not _public()._name(ref) for ref in item[2])
                   for item in self.selected_bindings)
            or len({item[0] for item in self.selected_bindings})
            != len(self.selected_bindings)
            or any(not _public()._name(item) for item in self.executed_nodes)
            or len(set(self.executed_nodes)) != len(self.executed_nodes)
            or len(self.executed_nodes) != (
                self.operation_count + self.memo_hit_count)
            or not set(self.executed_nodes).issubset(
                {item[0] for item in self.selected_bindings})
            or (self.unresolved_signature is not None
                and not _public()._name(self.unresolved_signature))
            or (self.lookup_count > len(self.executed_nodes)
                and self.unresolved_signature is None)
            or self.schema_version != _public().DAG_RECEIPT_SCHEMA):
        _public()._invalid("BAMF_DAG_RECEIPT_INVALID")


def validate_taskgoal(self) -> None:
    if (not _public()._name(self.goal_id)
            or not _public()._name(self.output_signature)
            or not isinstance(self.expression_or_holes, _public().DAGProgram)
            or not isinstance(self.budget, _public().DAGBudget)
            or not isinstance(self.source_visible_bindings, tuple)
            or any(not _public()._name(item) for item in self.source_visible_bindings)
            or tuple(sorted(set(self.source_visible_bindings)))
            != self.source_visible_bindings
            or not isinstance(self.allowed_operator_ids, tuple)
            or not self.allowed_operator_ids
            or any(not _public()._name(item) for item in self.allowed_operator_ids)
            or tuple(sorted(set(self.allowed_operator_ids)))
            != self.allowed_operator_ids
            or not isinstance(self.semantic_release, str)
            or not _public()._SHA.fullmatch(self.semantic_release)
            or not _public()._name(self.scope)
            or self.scope != self.expression_or_holes.scope
            or self.schema_version != _public().TASK_GOAL_SCHEMA):
        _public()._invalid("BAMF_TASK_GOAL_INVALID")


def validate_dagbudget(self) -> None:
    if (not all(type(value) is int and value > 0 for value in (
                self.max_nodes, self.max_depth, self.max_operations,
                self.max_decisions))
            or self.max_nodes > _public().MAX_DAG_NODES
            or self.max_depth > _public().MAX_DAG_DEPTH
            or self.max_operations > _public().MAX_DAG_NODES
            or self.max_decisions > _public().MAX_DAG_DECISIONS
            or self.schema_version != _public().DAG_BUDGET_SCHEMA):
        _public()._invalid("BAMF_DAG_BUDGET_INVALID")


def validate_dagprogram(self) -> None:
    if (not isinstance(self.nodes, tuple) or not self.nodes
            or len(self.nodes) > _public().MAX_DAG_NODES
            or any(not isinstance(item, _public().DAGNode) for item in self.nodes)
            or len({item.node_id for item in self.nodes}) != len(self.nodes)
            or not _public()._name(self.output_node_id)
            or self.output_node_id not in {
                item.node_id for item in self.nodes}
            or not _public()._name(self.scope)
            or any(item.scope != self.scope for item in self.nodes)
            or self.schema_version != _public().DAG_PROGRAM_SCHEMA):
        _public()._invalid("BAMF_DAG_PROGRAM_INVALID")


def validate_dagnode(self) -> None:
    if (not all(_public()._name(item) for item in (
                self.node_id, self.expected_output_type, self.scope))
            or (self.operator_id is not None
                and not _public()._name(self.operator_id))
            or not isinstance(self.operands, tuple)
            or len(self.operands) > _public().MAX_DAG_NODES
            or any(item is not None and not isinstance(item, _public().DAGOperand)
                   for item in self.operands)
            or not isinstance(self.candidate_operator_ids, tuple)
            or len(self.candidate_operator_ids) > _public().MAX_DAG_CANDIDATES
            or any(not _public()._name(item) for item in self.candidate_operator_ids)
            or self.candidate_operator_ids
            != tuple(sorted(set(self.candidate_operator_ids)))
            or not isinstance(self.candidate_operand_refs, tuple)
            or (self.candidate_operand_refs
                and len(self.candidate_operand_refs) != len(self.operands))
            or (self.candidate_operand_refs
                and any(group and self.operands[index] is not None
                        for index, group in enumerate(
                            self.candidate_operand_refs)))
            or any(not isinstance(group, tuple)
                   or len(group) > _public().MAX_DAG_CANDIDATES
                   or any(not isinstance(ref, _public().DAGOperand) for ref in group)
                   or tuple(sorted(set(group), key=lambda ref: ref.identity))
                   != group for group in self.candidate_operand_refs)
            or (any(ref is None for ref in self.operands)
                and (self.operator_id is not None
                     or not self.candidate_operand_refs
                     or any(not self.candidate_operand_refs[index]
                            for index, ref in enumerate(self.operands)
                            if ref is None)))
            or (self.operator_id is not None
                and (self.candidate_operand_refs or self.constraints))
            or not isinstance(self.constraints, tuple)
            or any(item not in (
                "SOURCE_VISIBLE", "TYPE_COMPATIBLE", "APPLICABLE")
                for item in self.constraints)
            or tuple(sorted(set(self.constraints))) != self.constraints
            or (self.operator_id is None) == (
                not self.candidate_operator_ids)
            or self.schema_version != _public().DAG_NODE_SCHEMA):
        _public()._invalid("BAMF_DAG_NODE_INVALID")


def validate_dagoperand(self) -> None:
    source = (self.source_handle is not None
              and all(item is None for item in (
                  self.frame_handle, self.frame_occurrence_id, self.role_id,
                  self.occurrence_index, self.result_node_id)))
    frame = (all(_public()._name(item) for item in (
                 self.frame_handle, self.frame_occurrence_id, self.role_id))
             and type(self.occurrence_index) is int
             and self.occurrence_index >= 0
             and self.type_name == "ConceptRef"
             and self.source_handle is None
             and self.result_node_id is None)
    result = (self.result_node_id is not None
              and all(item is None for item in (
                  self.source_handle, self.frame_handle,
                  self.frame_occurrence_id,
                  self.role_id, self.occurrence_index)))
    if (not isinstance(self.kind, _public().RefKind)
            or not _public()._name(self.type_name)
            or not (
                (self.kind is _public().RefKind.LITERAL and source
                 and _public()._name(self.source_handle))
                or (self.kind is _public().RefKind.INPUT and frame)
                or (self.kind is _public().RefKind.RESULT and result
                    and _public()._name(self.result_node_id)))
            or self.schema_version != _public().DAG_REF_SCHEMA):
        _public()._invalid("BAMF_DAG_OPERAND_INVALID")
