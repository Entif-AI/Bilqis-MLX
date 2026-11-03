"""C04.1 source-bound exact/cache/neural DAG routing without grade branches."""
from __future__ import annotations
from ...semantics._public_identity.facade_dependency import public_facade as _public_facade


def _public():
    return _public_facade("bilqis_mlx.runtime.cognitive_solver")


from dataclasses import asdict, dataclass, field
import re
from typing import Callable

from ...errors import BilqisError, ErrorBus, SCHOOL
from ...semantics.cognitive_dag import (
    DAGBudget, DAGReceipt, TaskGoal, execute_dag,
)
from ...semantics.cognitive_operators import (
    OperatorBinding, TypedValue, ValueState,
)
from ...semantics.domains import contract_digest
from ...semantics.memo import PureOperationMemo
from ..operator_registry import (
    RouteKind, RouteRegistry, default_route_registry,
)


from .contracts import SolveBudget


def _fills_declared_holes(candidate: TaskGoal, original: TaskGoal) -> bool:
    proposed = candidate.expression_or_holes
    declared = original.expression_or_holes
    if (proposed.output_node_id != declared.output_node_id
            or proposed.scope != declared.scope
            or {node.node_id for node in proposed.nodes}
            != {node.node_id for node in declared.nodes}):
        return False
    originals = {node.node_id: node for node in declared.nodes}
    for node in proposed.nodes:
        source = originals[node.node_id]
        if (node.scope != source.scope
                or node.expected_output_type != source.expected_output_type
                or len(node.operands) != len(source.operands)):
            return False
        if source.operator_id is not None:
            if node != source:
                return False
            continue
        if node.operator_id is None:
            if (not set(node.candidate_operator_ids).issubset(
                    source.candidate_operator_ids)
                    or node.constraints != source.constraints):
                return False
        elif node.operator_id not in source.candidate_operator_ids:
            return False
        for index, (fixed, chosen) in enumerate(zip(source.operands, node.operands)):
            if fixed is not None:
                if chosen != fixed:
                    return False
            elif chosen is not None:
                if chosen not in source.candidate_operand_refs[index]:
                    return False
            elif not set(node.candidate_operand_refs[index]).issubset(
                    source.candidate_operand_refs[index]):
                return False
    return True


def _goal_allowed(
    candidate: TaskGoal, original: TaskGoal, budget: SolveBudget,
) -> bool:
    return (
        _public()._fills_declared_holes(candidate, original)
        and candidate.semantic_release == original.semantic_release
        and candidate.scope == original.scope
        and candidate.output_signature == original.output_signature
        and set(candidate.source_visible_bindings).issubset(
            original.source_visible_bindings)
        and set(candidate.allowed_operator_ids).issubset(
            original.allowed_operator_ids)
        and all(getattr(candidate.budget, field_name)
                <= getattr(budget.dag_budget, field_name)
                for field_name in (
                    "max_nodes", "max_depth", "max_operations",
                    "max_decisions"))
    )


