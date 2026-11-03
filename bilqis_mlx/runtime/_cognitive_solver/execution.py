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


from .contracts import (GenerationBinding, QualifiedComposition, SolveBudget, NeuralRequest, NeuralProposal, SolveContext, _invalid)
from .results import CapabilityResult
from .policy import _goal_allowed


def _solve_task(
    task: TaskGoal, context: SolveContext,
    generation: GenerationBinding, budget: SolveBudget,
) -> CapabilityResult:
    """Exact first, qualified cached second, one bounded neural DAG last."""
    if (not isinstance(task, _public().TaskGoal)
            or not isinstance(context, _public().SolveContext)
            or not isinstance(generation, _public().GenerationBinding)
            or not isinstance(budget, _public().SolveBudget)):
        _public()._invalid("BAMF_C04_SOLVE_ARGUMENT_INVALID")
    binding = context.binding
    source_digest = _public().contract_digest(binding)
    if (task.semantic_release != binding.task.semantic_release
            or task.scope != binding.task.scope
            or generation.semantic_release != task.semantic_release
            or generation.source_binding_digest != source_digest
            or not _public()._goal_allowed(task, task, budget)):
        _public()._invalid("BAMF_C04_SOLVE_SOURCE_DRIFT")
    if len(context.qualified_compositions) > budget.max_cached_candidates:
        _public()._invalid("BAMF_C04_CACHED_CANDIDATE_BUDGET_EXCEEDED")
    receipts = []
    remaining_operations = task.budget.max_operations
    reserved_operations = 0

    def evaluate(goal: _public().TaskGoal):
        nonlocal remaining_operations, reserved_operations
        try:
            evaluated = _public().execute_dag(
                goal, binding, memo=context.memo,
                operation_limit=min(remaining_operations, goal.budget.max_operations))
        except _public().BilqisError:
            # A failed executor has no cost receipt; reserve all remaining compute.
            reserved_operations += remaining_operations
            remaining_operations = 0
            raise
        remaining_operations -= evaluated.receipt.operation_count
        receipts.append(evaluated.receipt)
        return evaluated

    def decode(callback, *args):
        try:
            return callback(*args)
        except (_public().BilqisError, ValueError):
            # Decoder construction is an external typed-payload boundary.
            return None

    local_refinement_calls = 0
    fallback_reason = None

    def result(answer: _public().TypedValue, route: _public().RouteKind, calls: int) -> _public().CapabilityResult:
        return _public().CapabilityResult(
            answer, route, tuple(receipts), calls,
            generation.generation_digest, source_digest,
            1.0 if route in (
                _public().RouteKind.EXACT, _public().RouteKind.CACHED_COMPOSITION,
                _public().RouteKind.DETERMINISTIC_FALLBACK) else None,
            _public().contract_digest(task), binding.frontier.rights_epoch,
            binding.frontier.correction_generation, task.budget.max_operations,
            reserved_operations, local_refinement_calls, fallback_reason)

    def qualified(cached: _public().QualifiedComposition) -> bool:
        return (
            cached.source_binding_digest == source_digest
            and cached.rights_epoch == binding.frontier.rights_epoch
            and cached.correction_generation
            == binding.frontier.correction_generation
            and context.qualification_verifier is not None
            and context.qualification_verifier(cached) is True
            and _public()._goal_allowed(cached.goal, task, budget))

    def execute_proposal(
        proposal: _public().NeuralProposal | None, request: _public().NeuralRequest,
    ):
        if proposal is None:
            return None, "BAMF_C04_NEURAL_NO_PROPOSAL"
        if not isinstance(proposal, _public().NeuralProposal):
            return None, "BAMF_C04_NEURAL_PROPOSAL_INVALID"
        if (proposal.source_binding_digest != source_digest
                or proposal.generation_digest
                != generation.generation_digest
                or proposal.unresolved_signature
                != request.unresolved_signature
                or not _public()._goal_allowed(proposal.goal, task, budget)):
            return None, "BAMF_C04_NEURAL_PROPOSAL_SCOPE_DRIFT"
        try:
            evaluated = evaluate(proposal.goal)
        except _public().BilqisError:
            return None, "BAMF_C04_NEURAL_DAG_REJECTED"
        if evaluated.answer.state is not _public().ValueState.VALUE:
            return evaluated, "BAMF_C04_NEURAL_UNRESOLVED"
        return evaluated, None

    ordered_cache = tuple(sorted(
        context.qualified_compositions,
        key=lambda item: (
            len(item.goal.expression_or_holes.nodes),
            item.qualification_receipt_sha256, item.goal.goal_id)))
    unresolved_answer = None
    unresolved_signature = "UNRESOLVED"
    neural_calls = 0
    for route in context.route_registry.specs:
        if route.kind is _public().RouteKind.EXACT:
            exact = evaluate(task)
            if exact.answer.state is _public().ValueState.VALUE:
                return result(exact.answer, _public().RouteKind.EXACT, 0)
            unresolved_answer = exact.answer
            unresolved_signature = (
                exact.receipt.unresolved_signature or "UNRESOLVED")
        elif route.kind is _public().RouteKind.CACHED_COMPOSITION:
            for cached in ordered_cache:
                if not qualified(cached):
                    continue
                try:
                    solved = evaluate(cached.goal)
                except _public().BilqisError:
                    fallback_reason = "BAMF_C04_CACHED_DAG_REJECTED"
                    continue
                if solved.answer.state is _public().ValueState.VALUE:
                    return result(
                        solved.answer, _public().RouteKind.CACHED_COMPOSITION, 0)
        elif route.kind is _public().RouteKind.NEURAL_COMPOSITION:
            if context.neural_proposer is None or budget.max_neural_calls == 0:
                continue
            request = _public().NeuralRequest(
                task.goal_id, unresolved_signature,
                source_digest, generation.generation_digest,
                task.allowed_operator_ids)
            neural_calls = 1
            neural, fallback_reason = execute_proposal(
                decode(context.neural_proposer, request), request)
            if neural is not None and neural.answer.state is _public().ValueState.VALUE:
                return result(
                    neural.answer, _public().RouteKind.NEURAL_COMPOSITION, neural_calls)
            if neural is not None:
                unresolved_answer = neural.answer
            if context.local_refiner is not None:
                for attempt in range(1, budget.max_local_refinements + 1):
                    local_refinement_calls += 1
                    refined, reason = execute_proposal(
                        decode(context.local_refiner, request, attempt), request)
                    if refined is not None:
                        unresolved_answer = refined.answer
                    if refined is not None and (
                            refined.answer.state is _public().ValueState.VALUE):
                        fallback_reason = None
                        return result(
                            refined.answer, _public().RouteKind.NEURAL_COMPOSITION,
                            neural_calls)
                    fallback_reason = reason
        elif route.kind is _public().RouteKind.DETERMINISTIC_FALLBACK:
            cached = context.deterministic_fallback
            if cached is None or not qualified(cached):
                continue
            try:
                fallback = evaluate(cached.goal)
            except _public().BilqisError:
                fallback_reason = "BAMF_C04_FALLBACK_DAG_REJECTED"
                continue
            if fallback.answer.state is _public().ValueState.VALUE:
                return result(
                    fallback.answer, _public().RouteKind.DETERMINISTIC_FALLBACK,
                    neural_calls)
        else:
            return result(
                unresolved_answer, _public().RouteKind.UNRESOLVED, neural_calls)
    _public()._invalid("BAMF_C04_ROUTE_REGISTRY_INCOMPLETE")


