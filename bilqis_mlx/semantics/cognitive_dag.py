"""Bounded, typed source-visible DAG execution without assessment labels."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import product
import re
from threading import RLock
from weakref import WeakKeyDictionary

from ..errors import ErrorBus, SEMANTIC_FRAME
from .cognitive_operators import (
    OperatorBinding, SourceKind, TypedValue, ValueState, _approved_frames,
    _authorize_inputs, _check_grant, _compute_after_authorization,
    _independent_applicability, _number_domain, operator_grant_digest,
)
from .domains import contract_digest
from .frame_schema import BindingState, FrameInstance
from .memo import PureOperationMemo


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
_MEMO_WITNESS_LOCK = RLock()
_MEMO_WITNESSES: WeakKeyDictionary[PureOperationMemo, dict[str, str]] = (
    WeakKeyDictionary())


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
        _validation.validate_dagoperand(self)

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
        _validation.validate_dagnode(self)

@dataclass(frozen=True)
class DAGProgram:
    nodes: tuple[DAGNode, ...]
    output_node_id: str
    scope: str
    schema_version: str = DAG_PROGRAM_SCHEMA

    def __post_init__(self) -> None:
        _validation.validate_dagprogram(self)

@dataclass(frozen=True)
class DAGBudget:
    max_nodes: int = MAX_DAG_NODES
    max_depth: int = MAX_DAG_DEPTH
    max_operations: int = MAX_DAG_NODES
    max_decisions: int = MAX_DAG_DECISIONS
    schema_version: str = DAG_BUDGET_SCHEMA

    def __post_init__(self) -> None:
        _validation.validate_dagbudget(self)

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
        _validation.validate_taskgoal(self)

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
        _validation.validate_dagreceipt(self)

@dataclass(frozen=True)
class DAGResult:
    answer: TypedValue
    receipt: DAGReceipt
    schema_version: str = DAG_RESULT_SCHEMA

    def __post_init__(self) -> None:
        _validation.validate_dagresult(self)

from ._cognitive_dag import record_validation as _validation
from ._cognitive_dag.memo import (
    _memo_get_verified, _memo_put_verified, _grant_record, _dependency_record, _consulted_dependencies,
)
from ._cognitive_dag.graph import (
    _topological, _visible_source,
)
from ._cognitive_dag.preparation import (
    _prepare,
)
from ._cognitive_dag.execution import (
    execute_dag,
)

# Keep historical public function identities and annotation resolution.
for _function in (
    _memo_get_verified, _memo_put_verified, _grant_record, _dependency_record, _consulted_dependencies,
    _topological, _visible_source,
    _prepare,
    execute_dag,
):
    _function.__module__ = __name__
del _function
