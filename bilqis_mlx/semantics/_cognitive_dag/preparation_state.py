"""Source-granted candidate preparation and bounded hole decisions."""
from __future__ import annotations
from .._public_identity.facade_dependency import public_facade
from ..cognitive_dag import (
    DAGOperand, DAGProgram, DAGBudget, DAGNode, TaskGoal, DAGResult, DAGReceipt,
    OperatorBinding, TypedValue, PureOperationMemo,
)


def _public():
    return public_facade("bilqis_mlx.semantics.cognitive_dag")


class _Preparation:
    def __init__(self, goal, binding, budget, by_id, approved):
        self.goal = goal
        self.binding = binding
        self.budget = budget
        self.by_id = by_id
        self.approved = approved
        self.prepared = {}
        self.visible = {}
        self.selected = []
        self.unresolved = None
        self.decisions = 0
        self.binding_checks = 0

    def validate_ref(self, ref: DAGOperand) -> None:
        if ref.kind is _public().RefKind.RESULT:
            predecessor = self.by_id.get(ref.result_node_id)
            if (predecessor is None
                    or predecessor.expected_output_type != ref.type_name):
                _public()._invalid("BAMF_DAG_RESULT_TYPE_INVALID")
        else:
            if ref.identity not in self.goal.source_visible_bindings:
                _public()._invalid("BAMF_DAG_SOURCE_NOT_TASK_VISIBLE")
            self.visible[ref.identity] = _public()._visible_source(ref, self.binding, self.approved)


    def applicable(self, spec, refs: tuple[DAGOperand | None, ...]) -> bool | None:
        values = tuple(
            self.visible[ref.identity]
            if ref is not None and ref.kind is not _public().RefKind.RESULT
            else None for ref in refs)
        return _public()._independent_applicability(spec, values, self.binding)


    def hole_candidate_viable(self, spec, node: DAGNode) -> bool:
        for index, ref in enumerate(node.operands):
            if ref is not None:
                continue
            if not any(
                choice.type_name == spec.signature.inputs[index]
                and self.applicable(
                    spec, node.operands[:index] + (choice,)
                    + node.operands[index + 1:]) is not False
                for choice in node.candidate_operand_refs[index]
            ):
                return False
        return self.applicable(spec, node.operands) is not False


    def candidates(self, node):
        if node.operator_id is None:
            candidates = tuple(
                self.binding.registry.resolve(name)
                for name in node.candidate_operator_ids)
        else:
            candidates = (self.binding.registry.resolve(node.operator_id),)
        if any(spec.operator_id not in self.goal.allowed_operator_ids
               for spec in candidates):
            _public()._invalid("BAMF_DAG_OPERATOR_NOT_TASK_ALLOWED")
        # Every proposed choice must be source-granted, not merely the
        # eventual unique binding. An unauthorized alternative must never
        # manufacture ambiguity that suppresses an otherwise legal answer.
        for spec in candidates:
            _public()._check_grant(
                "source:operator:" + spec.operator_id,
                _public().operator_grant_digest(spec), self.binding)
        for index, ref in enumerate(node.operands):
            if ref is not None:
                self.validate_ref(ref)
                continue
            for choice in node.candidate_operand_refs[index]:
                self.validate_ref(choice)
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
                 or self.binding.numeric_domain is not None)
            and (node.operator_id is not None
                 or self.hole_candidate_viable(spec, node)))
        if node.operator_id is not None and not matches:
            _public()._invalid("BAMF_DAG_OPERATOR_SIGNATURE_INVALID")
        if node.operator_id is None:
            self.decisions += (
                (1 if len(matches) > 1 else 0)
                + sum(1 for index, operand in enumerate(node.operands)
                      if operand is None
                      and len(node.candidate_operand_refs[index]) > 1))
            if self.decisions > self.budget.max_decisions:
                _public()._invalid("BAMF_DAG_DECISION_BUDGET_EXCEEDED")
        return matches


    def bind_open(self, node, matches):
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
            for refs in _public().product(*groups):
                if self.binding_checks >= _public().MAX_DAG_BINDING_CHECKS:
                    exhausted = True
                    break
                self.binding_checks += 1
                if self.applicable(spec, refs) is not False:
                    viable.append((spec, refs))
                    if len(viable) > 1:
                        break
            if exhausted or len(viable) > 1:
                break
        if not exhausted and len(viable) == 1:
            spec, refs = viable[0]
            self.prepared[node.node_id] = (spec, refs)
            self.selected.append((
                node.node_id, spec.operator_id,
                tuple(ref.identity for ref in refs)))
        else:
            self.unresolved = self.unresolved or (
                node.node_id + ":" + node.expected_output_type)


    def bind_fixed(self, node, matches):
        if (len(matches) != 1
                or (node.operator_id is None
                    and self.applicable(matches[0], node.operands) is False)):
            self.unresolved = self.unresolved or (
                node.node_id + ":" + node.expected_output_type)
            return
        self.prepared[node.node_id] = (matches[0], node.operands)
        self.selected.append((
            node.node_id, matches[0].operator_id,
            tuple(ref.identity for ref in node.operands)))


    def finish(self, order):
        _public()._authorize_inputs(tuple(self.visible.values()), self.binding)
        for spec, _ in self.prepared.values():
            _public()._check_grant(
                "source:operator:" + spec.operator_id,
                _public().operator_grant_digest(spec), self.binding)
            if spec.applicability == "FINITE_NUMBER":
                _public()._number_domain(self.binding)
        return order, self.prepared, self.visible, tuple(self.selected), self.unresolved
