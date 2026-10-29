"""C04.1 source-bound exact/cache/neural DAG routing without grade branches."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Callable

from ..errors import ErrorBus, SCHOOL
from ..semantics.cognitive_dag import (
    DAGBudget, DAGReceipt, TaskGoal, execute_dag,
)
from ..semantics.cognitive_operators import (
    OperatorBinding, TypedValue, ValueState,
)
from ..semantics.domains import contract_digest
from ..semantics.memo import PureOperationMemo
from .operator_registry import (
    RouteKind, RouteRegistry, default_route_registry,
)


GENERATION_BINDING_SCHEMA = "bilqis.c04.generation-binding/v1"
QUALIFIED_COMPOSITION_SCHEMA = "bilqis.c04.qualified-composition/v1"
SOLVE_BUDGET_SCHEMA = "bilqis.c04.solve-budget/v1"
SOLVE_CONTEXT_SCHEMA = "bilqis.c04.solve-context/v1"
NEURAL_REQUEST_SCHEMA = "bilqis.c04.neural-request/v1"
NEURAL_PROPOSAL_SCHEMA = "bilqis.c04.neural-proposal/v1"
CAPABILITY_RESULT_SCHEMA = "bilqis.c04.capability-result/v1"
MAX_CACHED_COMPOSITIONS = 16
MAX_NEURAL_CALLS = 1
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_SOLVER.INVALID, reason=reason)


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256.fullmatch(value))


def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value)


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
    schema_version: str = SOLVE_BUDGET_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.dag_budget, DAGBudget)
                or type(self.max_neural_calls) is not int
                or not 0 <= self.max_neural_calls <= MAX_NEURAL_CALLS
                or type(self.max_cached_candidates) is not int
                or not 0 <= self.max_cached_candidates
                <= MAX_CACHED_COMPOSITIONS
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
    schema_version: str = CAPABILITY_RESULT_SCHEMA

    def __post_init__(self) -> None:
        exact = self.route in (RouteKind.EXACT, RouteKind.CACHED_COMPOSITION)
        if (not isinstance(self.answer, TypedValue)
                or not isinstance(self.route, RouteKind)
                or not isinstance(self.dag_receipts, tuple)
                or not self.dag_receipts
                or any(not isinstance(item, DAGReceipt)
                       for item in self.dag_receipts)
                or type(self.neural_calls) is not int
                or self.neural_calls not in (0, MAX_NEURAL_CALLS)
                or not _sha(self.generation_digest)
                or not _sha(self.source_binding_digest)
                or (exact and (self.score != 1.0
                               or self.neural_calls != 0
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


def _goal_allowed(
    candidate: TaskGoal, original: TaskGoal, budget: SolveBudget,
) -> bool:
    return (
        candidate.semantic_release == original.semantic_release
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


def solve_task(
    task: TaskGoal, context: SolveContext,
    generation: GenerationBinding, budget: SolveBudget,
) -> CapabilityResult:
    """Exact first, qualified cached second, one bounded neural DAG last."""
    if (not isinstance(task, TaskGoal)
            or not isinstance(context, SolveContext)
            or not isinstance(generation, GenerationBinding)
            or not isinstance(budget, SolveBudget)):
        _invalid("BAMF_C04_SOLVE_ARGUMENT_INVALID")
    binding = context.binding
    source_digest = contract_digest(binding)
    if (task.semantic_release != binding.task.semantic_release
            or task.scope != binding.task.scope
            or generation.semantic_release != task.semantic_release
            or generation.source_binding_digest != source_digest
            or not _goal_allowed(task, task, budget)):
        _invalid("BAMF_C04_SOLVE_SOURCE_DRIFT")
    if len(context.qualified_compositions) > budget.max_cached_candidates:
        _invalid("BAMF_C04_CACHED_CANDIDATE_BUDGET_EXCEEDED")
    receipts = []

    def result(answer: TypedValue, route: RouteKind, calls: int) -> CapabilityResult:
        return CapabilityResult(
            answer, route, tuple(receipts), calls,
            generation.generation_digest, source_digest,
            1.0 if route in (
                RouteKind.EXACT, RouteKind.CACHED_COMPOSITION) else None)

    ordered_cache = tuple(sorted(
        context.qualified_compositions,
        key=lambda item: (
            len(item.goal.expression_or_holes.nodes),
            item.qualification_receipt_sha256, item.goal.goal_id)))
    unresolved_answer = None
    unresolved_signature = "UNRESOLVED"
    neural_calls = 0
    for route in context.route_registry.specs:
        if route.kind is RouteKind.EXACT:
            exact = execute_dag(task, binding, memo=context.memo)
            receipts.append(exact.receipt)
            if exact.answer.state is ValueState.VALUE:
                return result(exact.answer, RouteKind.EXACT, 0)
            unresolved_answer = exact.answer
            unresolved_signature = (
                exact.receipt.unresolved_signature or "UNRESOLVED")
        elif route.kind is RouteKind.CACHED_COMPOSITION:
            for cached in ordered_cache:
                if (cached.source_binding_digest != source_digest
                        or cached.rights_epoch != binding.frontier.rights_epoch
                        or cached.correction_generation
                        != binding.frontier.correction_generation
                        or context.qualification_verifier is None
                        or context.qualification_verifier(cached) is not True
                        or not _goal_allowed(cached.goal, task, budget)):
                    continue
                solved = execute_dag(cached.goal, binding, memo=context.memo)
                receipts.append(solved.receipt)
                if solved.answer.state is ValueState.VALUE:
                    return result(
                        solved.answer, RouteKind.CACHED_COMPOSITION, 0)
        elif route.kind is RouteKind.NEURAL_COMPOSITION:
            if context.neural_proposer is None or budget.max_neural_calls == 0:
                continue
            request = NeuralRequest(
                task.goal_id, unresolved_signature,
                source_digest, generation.generation_digest,
                task.allowed_operator_ids)
            neural_calls = 1
            proposal = context.neural_proposer(request)
            if proposal is None:
                continue
            if not isinstance(proposal, NeuralProposal):
                _invalid("BAMF_C04_NEURAL_PROPOSAL_INVALID")
            if (proposal.source_binding_digest != source_digest
                    or proposal.generation_digest
                    != generation.generation_digest
                    or proposal.unresolved_signature
                    != request.unresolved_signature
                    or not _goal_allowed(proposal.goal, task, budget)):
                _invalid("BAMF_C04_NEURAL_PROPOSAL_SCOPE_DRIFT")
            neural = execute_dag(proposal.goal, binding, memo=context.memo)
            receipts.append(neural.receipt)
            if neural.answer.state is ValueState.VALUE:
                return result(
                    neural.answer, RouteKind.NEURAL_COMPOSITION, neural_calls)
            unresolved_answer = neural.answer
        else:
            return result(
                unresolved_answer, RouteKind.UNRESOLVED, neural_calls)
    _invalid("BAMF_C04_ROUTE_REGISTRY_INCOMPLETE")
