"""B10/C04-owned refinement request classification from typed task structure."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from bilqis_mlx.semantics.cognitive_dag import RefKind, TaskGoal

from .capability_evaluation import _invalid


class RefinementRequestKind(str, Enum):
    ORDINARY = "ORDINARY"
    EXPLICIT_MEMBER = "EXPLICIT_MEMBER"
    UNRESOLVED_NESTED = "UNRESOLVED_NESTED"


@dataclass(frozen=True)
class RefinementRequestDisposition:
    kind: RefinementRequestKind
    requested_roles: tuple[str, ...]

    def __post_init__(self) -> None:
        if (type(self.kind) is not RefinementRequestKind
                or type(self.requested_roles) is not tuple
                or any(not isinstance(role, str) or not role
                       for role in self.requested_roles)
                or self.requested_roles != tuple(sorted(set(self.requested_roles)))):
            _invalid("BAMF_B10_REFINEMENT_REQUEST_DISPOSITION_INVALID")

    @property
    def explicit_member_question(self) -> bool:
        return self.kind is RefinementRequestKind.EXPLICIT_MEMBER

    @property
    def unresolved_nested_query(self) -> bool:
        return self.kind is RefinementRequestKind.UNRESOLVED_NESTED


def _operands(goal: TaskGoal):
    for node in goal.expression_or_holes.nodes:
        for operand in node.operands:
            if operand is not None:
                yield node, operand
        for group in node.candidate_operand_refs:
            for operand in group:
                yield node, operand


def refinement_request_disposition(goal: TaskGoal) -> RefinementRequestDisposition:
    """Derive B06 routing semantics from C04-owned typed task structure.

    An unresolved node that consumes an earlier result is a nested unresolved
    query. Otherwise a direct frame-member input is an explicit-member request.
    Flat source-literal and other tasks are ordinary. Callers supply no routing
    booleans or credentials.
    """
    if type(goal) is not TaskGoal:
        _invalid("BAMF_B10_REFINEMENT_REQUEST_INPUT_INVALID")
    members = tuple(
        operand for _node, operand in _operands(goal)
        if operand.kind is RefKind.INPUT)
    requested_roles = tuple(sorted({operand.role_id for operand in members}))
    nested = any(
        (node.operator_id is None or any(item is None for item in node.operands))
        and operand.kind is RefKind.RESULT
        for node, operand in _operands(goal)
    )
    if nested:
        kind = RefinementRequestKind.UNRESOLVED_NESTED
    elif members:
        kind = RefinementRequestKind.EXPLICIT_MEMBER
    else:
        kind = RefinementRequestKind.ORDINARY
    return RefinementRequestDisposition(kind, requested_roles)


__all__ = (
    "RefinementRequestDisposition", "RefinementRequestKind",
    "refinement_request_disposition",
)
