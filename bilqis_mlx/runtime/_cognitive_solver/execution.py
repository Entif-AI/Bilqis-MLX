"""Bounded exact/cache/neural cognitive solve execution."""
from __future__ import annotations

from ...errors import BilqisError
from ...semantics.cognitive_dag import TaskGoal, execute_dag
from ...semantics.cognitive_operators import TypedValue, ValueState
from ...semantics.domains import contract_digest
from ..operator_registry import RouteKind
from .common import MAX_NEURAL_CALLS, _invalid
from .records import (CapabilityResult, GenerationBinding, NeuralProposal, NeuralRequest,
    QualifiedComposition, SolveBudget, SolveContext)

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
            if (node.operator_id != source.operator_id
                    or node.candidate_operator_ids != source.candidate_operator_ids):
                return False
        elif node.operator_id is None:
            if (not set(node.candidate_operator_ids).issubset(
                    source.candidate_operator_ids)
                    or not node.candidate_operator_ids):
                return False
        elif node.operator_id not in source.candidate_operator_ids:
            return False
        elif node.candidate_operator_ids:
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
        unresolved = (node.operator_id is None
                      or any(operand is None for operand in node.operands))
        if (unresolved and node.constraints != source.constraints
                or not unresolved and node.constraints not in (source.constraints, ())):
            return False
    return True


def _goal_allowed(
    candidate: TaskGoal, original: TaskGoal, budget: SolveBudget,
) -> bool:
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
        return (
            cached.source_binding_digest == source_digest
            and cached.rights_epoch == binding.frontier.rights_epoch
            and cached.correction_generation
            == binding.frontier.correction_generation
            and context.qualification_verifier is not None
            and context.qualification_verifier(cached) is True
            and _goal_allowed(cached.goal, task, budget))

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
        context.qualified_compositions,
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
            neural, fallback_reason = execute_proposal(
                decode(context.neural_proposer, request), request)
            if neural is not None and neural.answer.state is ValueState.VALUE:
                return result(
                    neural.answer, RouteKind.NEURAL_COMPOSITION, neural_calls)
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
                            refined.answer.state is ValueState.VALUE):
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
