"""Gold-blind C04 lowering for bounded Factory-owned answer domains."""
from __future__ import annotations

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.cognitive_dag import (
    DAGNode, DAGOperand, DAGProgram, RefKind, task_goal_from_program,
)
from bilqis_mlx.semantics.cognitive_operators import (
    OperatorBinding, SourceKind, SourceOperand, TypedValue,
    default_registry, operator_grant_digest, source_operand_digest,
)
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
)
from bilqis_mlx.semantics.domains import contract_digest


_PURPOSE = "C04_SOLVER"
_PRINCIPAL = "bamf-c04-answer-choice"
_TENANT = "bamf-c05"
_JURISDICTION = "LOCAL"
_SUPPORTED = {
    "binary": ("Boolean", "SELECT_BOOLEAN"),
    "boolean_operator": ("OperatorId", "SELECT_OPERATOR_ID"),
    "numeric_active": ("Number", "SELECT_NUMBER"),
}


def _invalid(reason: str):
    ErrorBus.raise_(SCHOOL.BAMF_SOLVER.INVALID, reason=reason)


def _grant(handle, evidence, semantic_release, scope):
    return SourceGrant(
        handle, _PRINCIPAL, _TENANT, PUBLIC_FORMAL, semantic_release, evidence,
        (_PURPOSE,), (_JURISDICTION,), (scope,), 1, 1, 0, 0,
    )


def _answer_family(capability, answer_kind=None):
    matches = tuple(
        family for family in capability.answer_families
        if family.kind in _SUPPORTED
        and (answer_kind is None or family.kind == answer_kind))
    if len(matches) != 1:
        _invalid("BAMF_C04_ANSWER_CHOICE_FAMILY_UNSUPPORTED")
    family = matches[0]
    if not family.values or len(set(family.values)) != len(family.values):
        _invalid("BAMF_C04_ANSWER_CHOICE_DOMAIN_INVALID")
    return family


def lower_answer_choice_task_goal(
    row: dict, *, semantic_release: str, capability, **_,
):
    """Expose only the admitted answer domain; evaluator gold stays private."""
    if (not isinstance(row, dict) or "gold" in row
            or row.get("capability") != capability.capability_id
            or not isinstance(row.get("id"), str) or not row["id"]):
        _invalid("BAMF_C04_ANSWER_CHOICE_SOURCE_VIEW_INVALID")
    family = _answer_family(capability, row.get("answer_kind"))
    type_name, operator_id = _SUPPORTED[family.kind]
    release = semantic_release
    scope = capability.capability_id
    task = TaskScope(
        _PRINCIPAL, _TENANT, _PURPOSE, release, _JURISDICTION,
        scope, 0, 0, len(row.get("tokens", ())),
    )
    policy = ContextPolicy(
        "bamf-c04-answer-choice/v1", 1, 1,
        (_PURPOSE,), (PUBLIC_FORMAL,), (_JURISDICTION,),
        (scope,), (PUBLIC_FORMAL,), (), (),
    )
    registry = default_registry(release)
    spec = registry.resolve(operator_id)
    operands = []
    refs = []
    grants = [_grant(
        "source:operator:" + operator_id,
        operator_grant_digest(spec), release, scope)]
    row_id = row["id"]
    for value in family.values:
        payload = (value == "TRUE" if type_name == "Boolean"
                   else int(value) if type_name == "Number"
                   else value)
        if type_name == "Boolean" and value not in {"FALSE", "TRUE"}:
            _invalid("BAMF_C04_BINARY_DOMAIN_INVALID")
        handle = "source:answer-choice:" + contract_digest((
            row_id, family.kind, value))
        typed = TypedValue(type_name, payload, release, handle)
        source = SourceOperand(
            typed, SourceKind.TASK_VISIBLE,
            "source:answer-domain:" + scope,
            len(row.get("tokens", ())))
        operands.append(source)
        refs.append(DAGOperand(RefKind.LITERAL, type_name, source_handle=handle))
        grants.append(_grant(
            handle, source_operand_digest(source), release, scope))
    frontier = SourceFrontier(
        1, 1, tuple(sorted(grants, key=lambda item: item.source_handle)))
    binding = OperatorBinding(task, frontier, policy, registry, tuple(operands))
    node = DAGNode(
        "choice:root", operator_id, (None,), type_name, scope,
        candidate_operand_refs=(tuple(sorted(refs, key=lambda ref: ref.identity)),),
        constraints=("APPLICABLE", "SOURCE_VISIBLE", "TYPE_COMPATIBLE"),
    )
    program = DAGProgram((node,), node.node_id, scope)
    return task_goal_from_program(program, binding, goal_id=row_id), binding


__all__ = ("lower_answer_choice_task_goal",)
