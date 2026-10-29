"""Bounded, typed source-visible DAG execution without assessment labels."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from ..errors import ErrorBus, SEMANTIC_FRAME
from .cognitive_operators import (
    OperatorBinding, TypedValue, ValueState, _approved_frames,
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
                != self.lookup_count
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
                or len(self.executed_nodes) != self.lookup_count
                or not set(self.executed_nodes).issubset(
                    {item[0] for item in self.selected_bindings})
                or (self.unresolved_signature is not None
                    and not _name(self.unresolved_signature))
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


def _prepare(goal: TaskGoal, binding: OperatorBinding):
    """Validate the entire typed dependency graph before any computation."""
    if (not isinstance(goal, TaskGoal)
            or not isinstance(binding, OperatorBinding)):
        _invalid("BAMF_DAG_EXECUTION_INPUT_INVALID")
    program = goal.expression_or_holes
    budget = goal.budget
    output = next(
        node for node in program.nodes
        if node.node_id == program.output_node_id)
    if (goal.scope != binding.task.scope
            or goal.semantic_release != binding.task.semantic_release
            or goal.output_signature != output.expected_output_type):
        _invalid("BAMF_DAG_SCOPE_MISMATCH")
    order = _topological(program, budget)
    by_id = {node.node_id: node for node in program.nodes}
    approved = _approved_frames(binding)
    _authorize_inputs((), binding)
    prepared = {}
    visible = {}
    selected = []
    unresolved = None
    decisions = 0

    def validate_ref(ref: DAGOperand) -> None:
        if ref.kind is RefKind.RESULT:
            predecessor = by_id.get(ref.result_node_id)
            if (predecessor is None
                    or predecessor.expected_output_type != ref.type_name):
                _invalid("BAMF_DAG_RESULT_TYPE_INVALID")
        else:
            if ref.identity not in goal.source_visible_bindings:
                _invalid("BAMF_DAG_SOURCE_NOT_TASK_VISIBLE")
            visible[ref.identity] = _visible_source(ref, binding, approved)

    def applicable(spec, refs: tuple[DAGOperand | None, ...]) -> bool | None:
        values = tuple(
            visible[ref.identity]
            if ref is not None and ref.kind is not RefKind.RESULT
            else None for ref in refs)
        return _independent_applicability(spec, values, binding)

    def hole_candidate_viable(spec, node: DAGNode) -> bool:
        for index, ref in enumerate(node.operands):
            if ref is not None:
                continue
            if not any(
                choice.type_name == spec.signature.inputs[index]
                and applicable(
                    spec, node.operands[:index] + (choice,)
                    + node.operands[index + 1:]) is not False
                for choice in node.candidate_operand_refs[index]
            ):
                return False
        return applicable(spec, node.operands) is not False

    for node in order:
        if node.operator_id is None:
            candidates = tuple(
                binding.registry.resolve(name)
                for name in node.candidate_operator_ids)
        else:
            candidates = (binding.registry.resolve(node.operator_id),)
        if any(spec.operator_id not in goal.allowed_operator_ids
               for spec in candidates):
            _invalid("BAMF_DAG_OPERATOR_NOT_TASK_ALLOWED")
        resolved = list(node.operands)
        for index, ref in enumerate(node.operands):
            if ref is not None:
                validate_ref(ref)
                continue
            for choice in node.candidate_operand_refs[index]:
                validate_ref(choice)
        # Filter operators jointly with every fixed or open typed operand.
        matches = tuple(
            spec for spec in candidates
            if spec.signature.output == node.expected_output_type
            and len(spec.signature.inputs) == len(node.operands)
            and all(
                (operand.type_name == expected if operand is not None
                 else any(choice.type_name == expected for choice
                          in node.candidate_operand_refs[index]))
                for index, (operand, expected) in enumerate(
                    zip(node.operands, spec.signature.inputs)))
            and (node.operator_id is not None
                 or spec.applicability != "FINITE_NUMBER"
                 or binding.numeric_domain is not None)
            and (node.operator_id is not None
                 or hole_candidate_viable(spec, node)))
        if node.operator_id is not None and not matches:
            _invalid("BAMF_DAG_OPERATOR_SIGNATURE_INVALID")
        ambiguous_slots = 0
        for index, operand in enumerate(node.operands):
            if operand is not None:
                continue
            legal = tuple(
                choice for choice in node.candidate_operand_refs[index]
                if any(
                    choice.type_name == spec.signature.inputs[index]
                    and applicable(
                        spec, node.operands[:index] + (choice,)
                        + node.operands[index + 1:]) is not False
                    for spec in matches))
            if len(matches) == 1 and len(legal) == 1:
                resolved[index] = legal[0]
            elif len(legal) > 1:
                ambiguous_slots += 1
        if node.operator_id is None:
            decisions += ambiguous_slots + (1 if len(matches) > 1 else 0)
            if decisions > budget.max_decisions:
                _invalid("BAMF_DAG_DECISION_BUDGET_EXCEEDED")
        if (len(matches) != 1
                or any(operand is None for operand in resolved)
                or (node.operator_id is None and len(matches) == 1
                    and all(ref is not None for ref in resolved)
                    and applicable(matches[0], tuple(resolved)) is False)):
            unresolved = unresolved or (
                node.node_id + ":" + node.expected_output_type)
        if (len(matches) == 1
                and all(ref is not None for ref in resolved)
                and (node.operator_id is not None
                     or applicable(matches[0], tuple(resolved)) is not False)):
            prepared[node.node_id] = (matches[0], tuple(resolved))
            selected.append((node.node_id, matches[0].operator_id,
                             tuple(ref.identity for ref in resolved)))
    _authorize_inputs(tuple(visible.values()), binding)
    for spec, _ in prepared.values():
        _check_grant(
            "source:operator:" + spec.operator_id,
            operator_grant_digest(spec), binding)
        if spec.applicability == "FINITE_NUMBER":
            _number_domain(binding)
    return order, prepared, visible, tuple(selected), unresolved


def _grant_record(handle: str, binding: OperatorBinding):
    grant = next(
        (item for item in binding.frontier.grants
         if item.source_handle == handle), None)
    if grant is None:
        _invalid("BAMF_DAG_MEMO_SOURCE_GRANT_MISSING")
    return grant


def _dependency_record(
    ref: DAGOperand, value: TypedValue, binding: OperatorBinding,
    lineage: dict[str, str],
) -> tuple:
    if ref.kind is RefKind.RESULT:
        return (ref.identity, value, lineage[ref.result_node_id])
    if ref.kind is RefKind.LITERAL:
        source = next(
            item for item in binding.operands
            if item.typed.source_handle == ref.source_handle)
        return (ref.identity, value, source,
                _grant_record(ref.source_handle, binding))
    envelope = next(
        item for item in binding.frames
        if item.frame_handle == ref.frame_handle)
    member = next(
        item for item in envelope.members
        if (item.role_id, item.occurrence_index)
        == (ref.role_id, ref.occurrence_index))
    return (
        ref.identity, value, envelope, member,
        _grant_record(envelope.source_handle, binding),
        _grant_record(member.source_handle, binding))


def execute_dag(
    goal: TaskGoal,
    binding: OperatorBinding,
    *,
    memo: PureOperationMemo | None = None,
) -> DAGResult:
    """Run one fully source-validated typed DAG without neural or gold inputs."""
    if memo is not None and not isinstance(memo, PureOperationMemo):
        _invalid("BAMF_DAG_MEMO_INVALID")
    order, prepared, visible, selected, unresolved = _prepare(goal, binding)
    program = goal.expression_or_holes
    budget = goal.budget
    release = binding.task.semantic_release
    source_digest = contract_digest(binding)
    output_type = next(
        node.expected_output_type for node in program.nodes
        if node.node_id == program.output_node_id)
    computed = 0
    lookups = 0
    hits = 0
    executed: list[str] = []

    def finish(answer: TypedValue, reason: str | None = None) -> DAGResult:
        return DAGResult(answer, DAGReceipt(
            release, source_digest, computed, lookups, hits,
            selected, tuple(executed), reason))

    def unresolved_answer(node_id: str, type_name: str) -> DAGResult:
        return finish(
            TypedValue(output_type, None, release, state=ValueState.UNRESOLVED),
            node_id + ":" + type_name)

    if unresolved is not None:
        return finish(
            TypedValue(output_type, None, release, state=ValueState.UNRESOLVED),
            unresolved)

    results: dict[str, TypedValue] = {}
    lineage: dict[str, str] = {}
    for node in order:
        spec, refs = prepared[node.node_id]
        _check_grant(
            "source:operator:" + spec.operator_id,
            operator_grant_digest(spec), binding)
        numeric = (
            _number_domain(binding)
            if spec.applicability == "FINITE_NUMBER" else None)
        inputs = tuple(
            results[ref.result_node_id] if ref.kind is RefKind.RESULT
            else visible[ref.identity]
            for ref in refs)
        if any(value.state is not ValueState.VALUE for value in inputs):
            return unresolved_answer(node.node_id, node.expected_output_type)
        if (node.operator_id is None
                and _independent_applicability(
                    spec, inputs, binding) is False):
            return unresolved_answer(node.node_id, node.expected_output_type)
        dependencies = tuple(
            _dependency_record(ref, value, binding, lineage)
            for ref, value in zip(refs, inputs))
        authority = (
            binding.task, binding.policy,
            binding.frontier.rights_epoch,
            binding.frontier.correction_generation,
            _grant_record("source:operator:" + spec.operator_id, binding),
            numeric,
            _grant_record(binding.numeric_source_handle, binding)
            if numeric is not None else None,
        )
        key = PureOperationMemo.key(
            operator=spec, dependencies=dependencies, authority=authority)
        cached = memo.get(key) if memo is not None else None
        if cached is None and computed >= budget.max_operations:
            return unresolved_answer(node.node_id, node.expected_output_type)
        lookups += 1
        if cached is not None:
            if (not isinstance(cached, TypedValue)
                    or cached.type_name != node.expected_output_type
                    or cached.semantic_release != release
                    or cached.state not in (
                        ValueState.VALUE, ValueState.NONE)
                    or cached.source_handle is not None):
                _invalid("BAMF_DAG_MEMO_VALUE_INVALID")
            hits += 1
            value = cached
        else:
            computed += 1
            value = _compute_after_authorization(spec, inputs, binding)
            if memo is not None and value.state in (
                    ValueState.VALUE, ValueState.NONE):
                memo.put(key, value)
        results[node.node_id] = value
        lineage[node.node_id] = key
        executed.append(node.node_id)
        if value.state is not ValueState.VALUE and (
                node.node_id != program.output_node_id):
            return unresolved_answer(node.node_id, node.expected_output_type)
    return finish(results[program.output_node_id])
