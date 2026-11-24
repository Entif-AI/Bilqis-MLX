"""C04 solve result records and bounded proposal-scope validation."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from ..semantics.cognitive_dag import DAGReceipt, TaskGoal
from ..semantics.cognitive_operators import TypedValue, ValueState
from ..semantics.domains import contract_digest
from .cognitive_solver_common import (
    CAPABILITY_RESULT_SCHEMA, MAX_NEURAL_CALLS, SOLVE_REPLAY_SCHEMA,
    _invalid, _name, _sha,
)
from .operator_registry import RouteKind

_MAX_OPERATION_LIMIT = 64


@dataclass(frozen=True)
class CapabilityResult:
    answer: TypedValue
    route: RouteKind
    dag_receipts: tuple[DAGReceipt, ...]
    neural_calls: int
    generation_digest: str
    source_binding_digest: str
    score: float | None
    task_sha256: str
    rights_epoch: int
    correction_generation: int
    operation_limit: int
    reserved_operations: int
    local_refinement_calls: int = 0
    fallback_reason: str | None = None
    schema_version: str = CAPABILITY_RESULT_SCHEMA

    def __post_init__(self) -> None:
        exact = self.route in (
            RouteKind.EXACT, RouteKind.CACHED_COMPOSITION,
            RouteKind.DETERMINISTIC_FALLBACK)
        if (not isinstance(self.answer, TypedValue)
                or not isinstance(self.route, RouteKind)
                or not isinstance(self.dag_receipts, tuple)
                or not self.dag_receipts
                or any(not isinstance(item, DAGReceipt)
                       for item in self.dag_receipts)
                or type(self.neural_calls) is not int
                or self.neural_calls not in (0, MAX_NEURAL_CALLS)
                or type(self.local_refinement_calls) is not int
                or self.local_refinement_calls < 0
                or (self.fallback_reason is not None
                    and not _name(self.fallback_reason))
                or not _sha(self.generation_digest)
                or not _sha(self.source_binding_digest)
                or not _sha(self.task_sha256)
                or any(type(value) is not int or value < 0 for value in (
                    self.rights_epoch, self.correction_generation,
                    self.reserved_operations))
                or type(self.operation_limit) is not int
                or not 1 <= self.operation_limit <= _MAX_OPERATION_LIMIT
                or sum(item.operation_count for item in self.dag_receipts)
                + self.reserved_operations > self.operation_limit
                or any(item.source_binding_digest != self.source_binding_digest
                       or item.semantic_release != self.answer.semantic_release
                       for item in self.dag_receipts)
                or (exact and (self.score != 1.0
                               or (self.route is not
                                   RouteKind.DETERMINISTIC_FALLBACK
                                   and self.neural_calls != 0)
                               or self.answer.state is not ValueState.VALUE))
                or (self.route is RouteKind.NEURAL_COMPOSITION
                    and (self.neural_calls != 1
                         or self.score is not None
                         or self.answer.state is not ValueState.VALUE))
                or (self.route is RouteKind.UNRESOLVED
                    and (self.answer.state is ValueState.VALUE
                         or self.score is not None))
                or self.schema_version != CAPABILITY_RESULT_SCHEMA):
            _invalid("BAMF_C04_CAPABILITY_RESULT_INVALID")

    def replay_record(self) -> dict:
        """Export replay identities and measured costs without source/gold payloads."""
        return {
            "schema_version": SOLVE_REPLAY_SCHEMA,
            "task_sha256": self.task_sha256,
            "generation_digest": self.generation_digest,
            "source_binding_digest": self.source_binding_digest,
            "semantic_release": self.answer.semantic_release,
            "rights_epoch": self.rights_epoch,
            "correction_generation": self.correction_generation,
            "route": self.route.value,
            "dag_receipts": tuple(asdict(item) for item in self.dag_receipts),
            "costs": {
                "pure_operations": sum(item.operation_count for item in self.dag_receipts),
                "reserved_operations": self.reserved_operations,
                "operation_limit": self.operation_limit,
                "lookups": sum(item.lookup_count for item in self.dag_receipts),
                "memo_hits": sum(item.memo_hit_count for item in self.dag_receipts),
                "backbone_calls": self.neural_calls,
                "local_refinements": self.local_refinement_calls,
                "decoder_decisions": None,
            },
            "outcome": {
                "type": self.answer.type_name,
                "state": self.answer.state.value,
                "sha256": contract_digest(self.answer),
            },
            "fallback_reason": self.fallback_reason,
        }


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
            if node.operator_id != source.operator_id:
                return False
        elif node.operator_id is None:
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


def _goal_allowed(candidate: TaskGoal, original: TaskGoal, budget) -> bool:
    return (
        _fills_declared_holes(candidate, original)
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
