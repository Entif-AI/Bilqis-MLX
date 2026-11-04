"""Immutable cognitive-solver request, context and replay records."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable

from ...semantics.cognitive_dag import DAGBudget, DAGReceipt, TaskGoal
from ...semantics.cognitive_operators import OperatorBinding, TypedValue, ValueState
from ...semantics.domains import contract_digest
from ...semantics.memo import PureOperationMemo
from ..operator_registry import RouteKind, RouteRegistry, default_route_registry
from .common import (CAPABILITY_RESULT_SCHEMA, GENERATION_BINDING_SCHEMA,
    MAX_CACHED_COMPOSITIONS, MAX_NEURAL_CALLS, NEURAL_PROPOSAL_SCHEMA,
    NEURAL_REQUEST_SCHEMA, QUALIFIED_COMPOSITION_SCHEMA, SOLVE_BUDGET_SCHEMA,
    SOLVE_CONTEXT_SCHEMA, SOLVE_REPLAY_SCHEMA, _invalid, _name, _sha)

@dataclass(frozen=True)
class GenerationBinding:
    generation_digest: str
    semantic_release: str
    source_binding_digest: str
    schema_version: str = GENERATION_BINDING_SCHEMA

    def __post_init__(self) -> None:
        if (not all(_sha(item) for item in (
                self.generation_digest, self.semantic_release,
                self.source_binding_digest))
                or self.schema_version != GENERATION_BINDING_SCHEMA):
            _invalid("BAMF_C04_GENERATION_BINDING_INVALID")


@dataclass(frozen=True)
class QualifiedComposition:
    goal: TaskGoal
    source_binding_digest: str
    rights_epoch: int
    correction_generation: int
    qualification_receipt_sha256: str
    schema_version: str = QUALIFIED_COMPOSITION_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.goal, TaskGoal)
                or not _sha(self.source_binding_digest)
                or any(type(item) is not int or item < 0 for item in (
                    self.rights_epoch, self.correction_generation))
                or not _sha(self.qualification_receipt_sha256)
                or self.schema_version != QUALIFIED_COMPOSITION_SCHEMA):
            _invalid("BAMF_C04_QUALIFIED_COMPOSITION_INVALID")


@dataclass(frozen=True)
class SolveBudget:
    dag_budget: DAGBudget
    max_neural_calls: int = MAX_NEURAL_CALLS
    max_cached_candidates: int = MAX_CACHED_COMPOSITIONS
    max_local_refinements: int = 0
    schema_version: str = SOLVE_BUDGET_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.dag_budget, DAGBudget)
                or type(self.max_neural_calls) is not int
                or not 0 <= self.max_neural_calls <= MAX_NEURAL_CALLS
                or type(self.max_cached_candidates) is not int
                or not 0 <= self.max_cached_candidates
                <= MAX_CACHED_COMPOSITIONS
                or type(self.max_local_refinements) is not int
                or not 0 <= self.max_local_refinements
                <= self.dag_budget.max_decisions
                or self.schema_version != SOLVE_BUDGET_SCHEMA):
            _invalid("BAMF_C04_SOLVE_BUDGET_INVALID")


@dataclass(frozen=True)
class NeuralRequest:
    goal_id: str
    unresolved_signature: str
    source_binding_digest: str
    generation_digest: str
    allowed_operator_ids: tuple[str, ...]
    schema_version: str = NEURAL_REQUEST_SCHEMA

    def __post_init__(self) -> None:
        if (not _name(self.goal_id)
                or not _name(self.unresolved_signature)
                or not _sha(self.source_binding_digest)
                or not _sha(self.generation_digest)
                or not isinstance(self.allowed_operator_ids, tuple)
                or not self.allowed_operator_ids
                or tuple(sorted(set(self.allowed_operator_ids)))
                != self.allowed_operator_ids
                or self.schema_version != NEURAL_REQUEST_SCHEMA):
            _invalid("BAMF_C04_NEURAL_REQUEST_INVALID")


@dataclass(frozen=True)
class NeuralProposal:
    goal: TaskGoal
    source_binding_digest: str
    generation_digest: str
    unresolved_signature: str
    proposal_receipt_sha256: str
    schema_version: str = NEURAL_PROPOSAL_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.goal, TaskGoal)
                or not _sha(self.source_binding_digest)
                or not _sha(self.generation_digest)
                or not _name(self.unresolved_signature)
                or not _sha(self.proposal_receipt_sha256)
                or self.schema_version != NEURAL_PROPOSAL_SCHEMA):
            _invalid("BAMF_C04_NEURAL_PROPOSAL_INVALID")


@dataclass(frozen=True)
class SolveContext:
    binding: OperatorBinding
    qualified_compositions: tuple[QualifiedComposition, ...] = ()
    qualification_verifier: Callable[[QualifiedComposition], bool] | None = None
    neural_proposer: Callable[[NeuralRequest], NeuralProposal | None] | None = None
    local_refiner: Callable[[NeuralRequest, int], NeuralProposal | None] | None = None
    deterministic_fallback: QualifiedComposition | None = None
    memo: PureOperationMemo | None = None
    route_registry: RouteRegistry = field(default_factory=default_route_registry)
    schema_version: str = SOLVE_CONTEXT_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.binding, OperatorBinding)
                or not isinstance(self.qualified_compositions, tuple)
                or any(not isinstance(item, QualifiedComposition)
                       for item in self.qualified_compositions)
                or (self.qualification_verifier is not None
                    and not callable(self.qualification_verifier))
                or (self.neural_proposer is not None
                    and not callable(self.neural_proposer))
                or (self.local_refiner is not None
                    and not callable(self.local_refiner))
                or (self.deterministic_fallback is not None
                    and not isinstance(self.deterministic_fallback,
                                       QualifiedComposition))
                or (self.memo is not None
                    and not isinstance(self.memo, PureOperationMemo))
                or not isinstance(self.route_registry, RouteRegistry)
                or self.schema_version != SOLVE_CONTEXT_SCHEMA):
            _invalid("BAMF_C04_SOLVE_CONTEXT_INVALID")


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
                or not 1 <= self.operation_limit <= 64
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
