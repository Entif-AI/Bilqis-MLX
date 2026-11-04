"""Precompute-free validation and bounded hole binding for cognitive DAGs."""
from __future__ import annotations

from itertools import product

from ..cognitive_operators.authorization import (
    _approved_frames, _authorize_inputs, _check_grant,
    _independent_applicability, _number_domain,
)
from ..cognitive_operators.registry import OperatorBinding, operator_grant_digest
from .contracts import DAGNode, DAGOperand, RefKind, MAX_DAG_BINDING_CHECKS, _invalid
from .goals import TaskGoal
from .topology import _topological, _visible_source

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
    binding_checks = 0

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
        # Every proposed choice must be source-granted, not merely the
        # eventual unique binding. An unauthorized alternative must never
        # manufacture ambiguity that suppresses an otherwise legal answer.
        for spec in candidates:
            _check_grant(
                "source:operator:" + spec.operator_id,
                operator_grant_digest(spec), binding)
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
        decisions += (
            (1 if node.operator_id is None and len(matches) > 1 else 0)
            + sum(1 for index, operand in enumerate(node.operands)
                  if operand is None
                  and len(node.candidate_operand_refs[index]) > 1))
        if decisions > budget.max_decisions:
            _invalid("BAMF_DAG_DECISION_BUDGET_EXCEEDED")
        if any(ref is None for ref in node.operands):
            # Bounded *local* legality check, not speculative DAG/tree search.
            # Never execute candidates or inspect evaluation gold.
            viable = []
            exhausted = False
            for spec in matches:
                groups = tuple(
                    (ref,) if ref is not None else tuple(
                        choice for choice in node.candidate_operand_refs[index]
                        if choice.type_name == spec.signature.inputs[index])
                    for index, ref in enumerate(node.operands))
                for refs in product(*groups):
                    if binding_checks >= MAX_DAG_BINDING_CHECKS:
                        exhausted = True
                        break
                    binding_checks += 1
                    if applicable(spec, refs) is not False:
                        viable.append((spec, refs))
                        if len(viable) > 1:
                            break
                if exhausted or len(viable) > 1:
                    break
            if not exhausted and len(viable) == 1:
                spec, refs = viable[0]
                prepared[node.node_id] = (spec, refs)
                selected.append((
                    node.node_id, spec.operator_id,
                    tuple(ref.identity for ref in refs)))
            else:
                unresolved = unresolved or (
                    node.node_id + ":" + node.expected_output_type)
            continue
        if (len(matches) != 1
                or (node.operator_id is None
                    and applicable(matches[0], node.operands) is False)):
            unresolved = unresolved or (
                node.node_id + ":" + node.expected_output_type)
            continue
        prepared[node.node_id] = (matches[0], node.operands)
        selected.append((
            node.node_id, matches[0].operator_id,
            tuple(ref.identity for ref in node.operands)))
    _authorize_inputs(tuple(visible.values()), binding)
    for spec, _ in prepared.values():
        _check_grant(
            "source:operator:" + spec.operator_id,
            operator_grant_digest(spec), binding)
        if spec.applicability == "FINITE_NUMBER":
            _number_domain(binding)
    return order, prepared, visible, tuple(selected), unresolved
