"""Immutable DAG records and bounded structural limits."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from ...errors import ErrorBus, SEMANTIC_FRAME

DAG_REF_SCHEMA = "bilqis.cognitive-dag-operand/v1"
DAG_NODE_SCHEMA = "bilqis.cognitive-dag-node/v1"
DAG_PROGRAM_SCHEMA = "bilqis.cognitive-dag-program/v1"
DAG_BUDGET_SCHEMA = "bilqis.cognitive-dag-budget/v1"
DAG_RECEIPT_SCHEMA = "bilqis.cognitive-dag-receipt/v1"
DAG_RESULT_SCHEMA = "bilqis.cognitive-dag-result/v1"
TASK_GOAL_SCHEMA = "bilqis.task-goal/v1"
MAX_DAG_NODES = 64
MAX_DAG_DEPTH = 8
MAX_DAG_DECISIONS = 64
MAX_DAG_CANDIDATES = 64
MAX_DAG_BINDING_CHECKS = 4096
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<dag>", span_start=0, span_end=0,
    )


def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value)


class RefKind(str, Enum):
    LITERAL = "LITERAL"
    INPUT = "INPUT"
    RESULT = "RESULT"


@dataclass(frozen=True)
class DAGOperand:
    kind: RefKind
    type_name: str
    source_handle: str | None = None
    frame_handle: str | None = None
    frame_occurrence_id: str | None = None
    role_id: str | None = None
    occurrence_index: int | None = None
    result_node_id: str | None = None
    schema_version: str = DAG_REF_SCHEMA

    def __post_init__(self) -> None:
        source = (self.source_handle is not None
                  and all(item is None for item in (
                      self.frame_handle, self.frame_occurrence_id, self.role_id,
                      self.occurrence_index, self.result_node_id)))
        frame = (all(_name(item) for item in (
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
        if (not isinstance(self.kind, RefKind)
                or not _name(self.type_name)
                or not (
                    (self.kind is RefKind.LITERAL and source
                     and _name(self.source_handle))
                    or (self.kind is RefKind.INPUT and frame)
                    or (self.kind is RefKind.RESULT and result
                        and _name(self.result_node_id)))
                or self.schema_version != DAG_REF_SCHEMA):
            _invalid("BAMF_DAG_OPERAND_INVALID")

    @property
    def identity(self) -> str:
        if self.kind is RefKind.LITERAL:
            return "literal:" + self.source_handle
        if self.kind is RefKind.RESULT:
            return "result:" + self.result_node_id
        return "input:" + self.frame_occurrence_id + ":" + self.role_id + ":" + str(
            self.occurrence_index)


@dataclass(frozen=True)
class DAGNode:
    node_id: str
    operator_id: str | None
    operands: tuple[DAGOperand | None, ...]
    expected_output_type: str
    scope: str
    candidate_operator_ids: tuple[str, ...] = ()
    candidate_operand_refs: tuple[tuple[DAGOperand, ...], ...] = ()
    constraints: tuple[str, ...] = ()
    schema_version: str = DAG_NODE_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_name(item) for item in (
                    self.node_id, self.expected_output_type, self.scope))
                or (self.operator_id is not None
                    and not _name(self.operator_id))
                or not isinstance(self.operands, tuple)
                or len(self.operands) > MAX_DAG_NODES
                or any(item is not None and not isinstance(item, DAGOperand)
                       for item in self.operands)
                or not isinstance(self.candidate_operator_ids, tuple)
                or len(self.candidate_operator_ids) > MAX_DAG_CANDIDATES
                or any(not _name(item) for item in self.candidate_operator_ids)
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
                       or len(group) > MAX_DAG_CANDIDATES
                       or any(not isinstance(ref, DAGOperand) for ref in group)
                       or tuple(sorted(set(group), key=lambda ref: ref.identity))
                       != group for group in self.candidate_operand_refs)
                or (any(ref is None for ref in self.operands)
                    and (not self.candidate_operand_refs
                         or any(not self.candidate_operand_refs[index]
                                for index, ref in enumerate(self.operands)
                                if ref is None)))
                or (self.operator_id is not None
                    and self.candidate_operator_ids)
                or (self.operator_id is not None
                    and self.constraints and not any(ref is None for ref in self.operands))
                or not isinstance(self.constraints, tuple)
                or any(item not in (
                    "SOURCE_VISIBLE", "TYPE_COMPATIBLE", "APPLICABLE")
                    for item in self.constraints)
                or tuple(sorted(set(self.constraints))) != self.constraints
                or (self.operator_id is None and not self.candidate_operator_ids)
                or self.schema_version != DAG_NODE_SCHEMA):
            _invalid("BAMF_DAG_NODE_INVALID")


@dataclass(frozen=True)
class DAGProgram:
    nodes: tuple[DAGNode, ...]
    output_node_id: str
    scope: str
    schema_version: str = DAG_PROGRAM_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.nodes, tuple) or not self.nodes
                or len(self.nodes) > MAX_DAG_NODES
                or any(not isinstance(item, DAGNode) for item in self.nodes)
                or len({item.node_id for item in self.nodes}) != len(self.nodes)
                or not _name(self.output_node_id)
                or self.output_node_id not in {
                    item.node_id for item in self.nodes}
                or not _name(self.scope)
                or any(item.scope != self.scope for item in self.nodes)
                or self.schema_version != DAG_PROGRAM_SCHEMA):
            _invalid("BAMF_DAG_PROGRAM_INVALID")


@dataclass(frozen=True)
class DAGBudget:
    max_nodes: int = MAX_DAG_NODES
    max_depth: int = MAX_DAG_DEPTH
    max_operations: int = MAX_DAG_NODES
    max_decisions: int = MAX_DAG_DECISIONS
    schema_version: str = DAG_BUDGET_SCHEMA

    def __post_init__(self) -> None:
        if (not all(type(value) is int and value > 0 for value in (
                    self.max_nodes, self.max_depth, self.max_operations,
                    self.max_decisions))
                or self.max_nodes > MAX_DAG_NODES
                or self.max_depth > MAX_DAG_DEPTH
                or self.max_operations > MAX_DAG_NODES
                or self.max_decisions > MAX_DAG_DECISIONS
                or self.schema_version != DAG_BUDGET_SCHEMA):
            _invalid("BAMF_DAG_BUDGET_INVALID")
