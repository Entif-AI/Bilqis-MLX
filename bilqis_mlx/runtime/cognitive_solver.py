"""C04.1 source-bound exact/cache/neural DAG routing without grade branches."""
from __future__ import annotations

from ..errors import BilqisError
from ..semantics.cognitive_dag import TaskGoal, execute_dag
from ..semantics.cognitive_operators import TypedValue, ValueState
from ..semantics.domains import contract_digest
from .operator_registry import RouteKind
from .cognitive_solver_contracts import (
    CAPABILITY_RESULT_SCHEMA, GENERATION_BINDING_SCHEMA, MAX_CACHED_COMPOSITIONS,
    MAX_NEURAL_CALLS, NEURAL_PROPOSAL_SCHEMA, NEURAL_REQUEST_SCHEMA,
    QUALIFIED_COMPOSITION_SCHEMA, SOLVE_BUDGET_SCHEMA, SOLVE_CONTEXT_SCHEMA,
    SOLVE_REPLAY_SCHEMA, CapabilityResult, GenerationBinding, NeuralProposal,
    NeuralRequest, QualifiedComposition, SolveBudget, SolveContext, _goal_allowed,
    _invalid,
)

# Preserve the historical public record identity after physical compartmentalization.
for _record in (
    GenerationBinding, QualifiedComposition, SolveBudget, NeuralRequest,
    NeuralProposal, SolveContext, CapabilityResult,
):
    _record.__module__ = __name__

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
    if (len(context.operator_composition_artifact_owner.compositions)
            > budget.max_cached_candidates):
        _invalid("BAMF_C04_CACHED_CANDIDATE_BUDGET_EXCEEDED")
    receipts = []
    remaining_operations = task.budget.max_operations
    reserved_operations = 0

    def evaluate(goal: TaskGoal):
        nonlocal remaining_operations, reserved_operations
        try:
            evaluated = execute_dag(
                goal, binding, memo=context.memo,
                operation_limit=min(remaining_operations, goal.budget.max_operations))
        except BilqisError:
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
        except (BilqisError, ValueError):
            # Decoder construction is an external typed-payload boundary.
            return None

    local_refinement_calls = 0
    fallback_reason = None

    def result(answer: TypedValue, route: RouteKind, calls: int) -> CapabilityResult:
        return CapabilityResult(
            answer, route, tuple(receipts), calls,
            generation.generation_digest, source_digest,
            1.0 if route in (
                RouteKind.EXACT, RouteKind.CACHED_COMPOSITION,
                RouteKind.DETERMINISTIC_FALLBACK) else None,
            contract_digest(task), binding.frontier.rights_epoch,
            binding.frontier.correction_generation, task.budget.max_operations,
            reserved_operations, local_refinement_calls, fallback_reason)

    def qualified(cached: QualifiedComposition) -> bool:
        context.operator_composition_artifact_owner.require(cached, binding)
        verified = (
            context.operator_composition_artifact_owner.is_materialized(cached)
            or (context.qualification_verifier is not None
                and context.qualification_verifier(cached) is True)
        )
        return (
            cached.source_binding_digest == source_digest
            and cached.generation_digest == generation.generation_digest
            and cached.rights_epoch == binding.frontier.rights_epoch
            and cached.correction_generation
            == binding.frontier.correction_generation
            and verified
            and _goal_allowed(cached.goal, task, budget))

    def retain_validated(proposal: NeuralProposal) -> None:
        context.operator_composition_artifact_owner.remember(
            QualifiedComposition(
                proposal.goal,
                source_digest,
                generation.generation_digest,
                binding.frontier.rights_epoch,
                binding.frontier.correction_generation,
                proposal.proposal_receipt_sha256,
            ),
            binding,
            max_cached_candidates=budget.max_cached_candidates,
        )

    def execute_proposal(
        proposal: NeuralProposal | None, request: NeuralRequest,
    ):
        if proposal is None:
            return None, "BAMF_C04_NEURAL_NO_PROPOSAL"
        if not isinstance(proposal, NeuralProposal):
            return None, "BAMF_C04_NEURAL_PROPOSAL_INVALID"
        if (proposal.source_binding_digest != source_digest
                or proposal.generation_digest
                != generation.generation_digest
                or proposal.unresolved_signature
                != request.unresolved_signature
                or not _goal_allowed(proposal.goal, task, budget)):
            return None, "BAMF_C04_NEURAL_PROPOSAL_SCOPE_DRIFT"
        try:
            evaluated = evaluate(proposal.goal)
        except BilqisError:
            return None, "BAMF_C04_NEURAL_DAG_REJECTED"
        if evaluated.answer.state is not ValueState.VALUE:
            return evaluated, "BAMF_C04_NEURAL_UNRESOLVED"
        return evaluated, None

    ordered_cache = tuple(sorted(
        context.operator_composition_artifact_owner.compositions,
        key=lambda item: (
            len(item.goal.expression_or_holes.nodes),
            item.qualification_receipt_sha256, item.goal.goal_id)))
    unresolved_answer = None
    unresolved_signature = "UNRESOLVED"
    neural_calls = 0
    for route in context.route_registry.specs:
        if route.kind is RouteKind.EXACT:
            exact = evaluate(task)
            if exact.answer.state is ValueState.VALUE:
                return result(exact.answer, RouteKind.EXACT, 0)
            unresolved_answer = exact.answer
            unresolved_signature = (
                exact.receipt.unresolved_signature or "UNRESOLVED")
        elif route.kind is RouteKind.CACHED_COMPOSITION:
            for cached in ordered_cache:
                if not qualified(cached):
                    continue
                try:
                    solved = evaluate(cached.goal)
                except BilqisError:
                    fallback_reason = "BAMF_C04_CACHED_DAG_REJECTED"
                    continue
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
            proposal = decode(context.neural_proposer, request)
            neural, fallback_reason = execute_proposal(proposal, request)
            if neural is not None and neural.answer.state is ValueState.VALUE:
                retain_validated(proposal)
                return result(
                    neural.answer, RouteKind.NEURAL_COMPOSITION, neural_calls)
            if neural is not None:
                unresolved_answer = neural.answer
            if context.local_refiner is not None:
                for attempt in range(1, budget.max_local_refinements + 1):
                    local_refinement_calls += 1
                    proposal = decode(context.local_refiner, request, attempt)
                    refined, reason = execute_proposal(proposal, request)
                    if refined is not None:
                        unresolved_answer = refined.answer
                    if refined is not None and (
                            refined.answer.state is ValueState.VALUE):
                        retain_validated(proposal)
                        fallback_reason = None
                        return result(
                            refined.answer, RouteKind.NEURAL_COMPOSITION,
                            neural_calls)
                    fallback_reason = reason
        elif route.kind is RouteKind.DETERMINISTIC_FALLBACK:
            cached = context.deterministic_fallback
            if cached is None or not qualified(cached):
                continue
            try:
                fallback = evaluate(cached.goal)
            except BilqisError:
                fallback_reason = "BAMF_C04_FALLBACK_DAG_REJECTED"
                continue
            if fallback.answer.state is ValueState.VALUE:
                return result(
                    fallback.answer, RouteKind.DETERMINISTIC_FALLBACK,
                    neural_calls)
        else:
            return result(
                unresolved_answer, RouteKind.UNRESOLVED, neural_calls)
    _invalid("BAMF_C04_ROUTE_REGISTRY_INCOMPLETE")
