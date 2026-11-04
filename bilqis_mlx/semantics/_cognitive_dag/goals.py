"""Task-goal lowering and execution receipt contracts."""
from __future__ import annotations

from dataclasses import dataclass

from ..cognitive_operators.registry import OperatorBinding
from ..cognitive_operators.types import TypedValue, ValueState
from .contracts import (
    DAGBudget, DAGProgram, RefKind, DAG_RECEIPT_SCHEMA, DAG_RESULT_SCHEMA,
    MAX_DAG_NODES, TASK_GOAL_SCHEMA, _SHA, _invalid, _name,
)

@dataclass(frozen=True)
class TaskGoal:
    goal_id: str
    output_signature: str
    source_visible_bindings: tuple[str, ...]
    expression_or_holes: DAGProgram
    allowed_operator_ids: tuple[str, ...]
    budget: DAGBudget
    semantic_release: str
    scope: str
    schema_version: str = TASK_GOAL_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.goal_id)
                or not _name(self.output_signature)
                or not isinstance(self.expression_or_holes, DAGProgram)
                or not isinstance(self.budget, DAGBudget)
                or not isinstance(self.source_visible_bindings, tuple)
                or any(not _name(item) for item in self.source_visible_bindings)
                or tuple(sorted(set(self.source_visible_bindings)))
                != self.source_visible_bindings
                or not isinstance(self.allowed_operator_ids, tuple)
                or not self.allowed_operator_ids
                or any(not _name(item) for item in self.allowed_operator_ids)
                or tuple(sorted(set(self.allowed_operator_ids)))
                != self.allowed_operator_ids
                or not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or not _name(self.scope)
                or self.scope != self.expression_or_holes.scope
                or self.schema_version != TASK_GOAL_SCHEMA):
            _invalid("BAMF_TASK_GOAL_INVALID")


def task_goal_from_program(
    program: DAGProgram,
    binding: OperatorBinding,
    *,
    goal_id: str,
    budget: DAGBudget | None = None,
) -> TaskGoal:
    """Build the bounded task contract from a source-qualified DAG and binding.

    This is structural lowering only. It derives visible source handles,
    operator allowlisting, output type and semantic/scope identity from the
    supplied program and already-authorized binding. It never receives or
    derives evaluator gold.
    """
    if (not isinstance(program, DAGProgram)
            or not isinstance(binding, OperatorBinding)
            or not _name(goal_id)
            or (budget is not None and not isinstance(budget, DAGBudget))):
        _invalid("BAMF_TASK_GOAL_LOWERING_INPUT_INVALID")
    refs = tuple(
        ref for node in program.nodes
        for ref in (
            tuple(ref for ref in node.operands if ref is not None)
            + tuple(ref for group in node.candidate_operand_refs for ref in group)
        )
        if ref.kind is not RefKind.RESULT
    )
    operators = tuple(sorted(set(
        operator_id for node in program.nodes
        for operator_id in (
            (node.operator_id,) if node.operator_id is not None
            else node.candidate_operator_ids
        )
    )))
    output_type = next((
        node.expected_output_type for node in program.nodes
        if node.node_id == program.output_node_id
    ), None)
    if output_type is None or not operators:
        _invalid("BAMF_TASK_GOAL_LOWERING_PROGRAM_INVALID")
    return TaskGoal(
        goal_id,
        output_type,
        tuple(sorted(set(ref.identity for ref in refs))),
        program,
        operators,
        budget or DAGBudget(),
        binding.task.semantic_release,
        program.scope,
    )


@dataclass(frozen=True)
class DAGReceipt:
    semantic_release: str
    source_binding_digest: str
    operation_count: int
    lookup_count: int
    memo_hit_count: int
    selected_bindings: tuple[tuple[str, str, tuple[str, ...]], ...]
    executed_nodes: tuple[str, ...]
    unresolved_signature: str | None = None
    schema_version: str = DAG_RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        if (not all(isinstance(item, str) and _SHA.fullmatch(item) for item in (
                    self.semantic_release, self.source_binding_digest))
                or not all(type(value) is int and value >= 0 for value in (
                    self.operation_count, self.lookup_count,
                    self.memo_hit_count))
                or self.lookup_count > MAX_DAG_NODES
                or self.memo_hit_count > self.lookup_count
                or self.operation_count + self.memo_hit_count
                > self.lookup_count
                or self.lookup_count - (
                    self.operation_count + self.memo_hit_count) > 1
                or not isinstance(self.selected_bindings, tuple)
                or not isinstance(self.executed_nodes, tuple)
                or any(not isinstance(item, tuple) or len(item) != 3
                       or not _name(item[0]) or not _name(item[1])
                       or not isinstance(item[2], tuple)
                       or any(not _name(ref) for ref in item[2])
                       for item in self.selected_bindings)
                or len({item[0] for item in self.selected_bindings})
                != len(self.selected_bindings)
                or any(not _name(item) for item in self.executed_nodes)
                or len(set(self.executed_nodes)) != len(self.executed_nodes)
                or len(self.executed_nodes) != (
                    self.operation_count + self.memo_hit_count)
                or not set(self.executed_nodes).issubset(
                    {item[0] for item in self.selected_bindings})
                or (self.unresolved_signature is not None
                    and not _name(self.unresolved_signature))
                or (self.lookup_count > len(self.executed_nodes)
                    and self.unresolved_signature is None)
                or self.schema_version != DAG_RECEIPT_SCHEMA):
            _invalid("BAMF_DAG_RECEIPT_INVALID")


@dataclass(frozen=True)
class DAGResult:
    answer: TypedValue
    receipt: DAGReceipt
    schema_version: str = DAG_RESULT_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.answer, TypedValue)
                or not isinstance(self.receipt, DAGReceipt)
                or self.answer.semantic_release
                != self.receipt.semantic_release
                or (self.answer.state is ValueState.UNRESOLVED)
                != (self.receipt.unresolved_signature is not None)
                or self.schema_version != DAG_RESULT_SCHEMA):
            _invalid("BAMF_DAG_RESULT_INVALID")
