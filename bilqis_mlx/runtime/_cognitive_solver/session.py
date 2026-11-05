"""C04.1 per-solve operation accounting, qualification and proposal state."""
from __future__ import annotations
from .execution import _public


class _SolveSession:
    def __init__(self, task, context, generation, budget, binding, source_digest):
        self.task = task
        self.context = context
        self.generation = generation
        self.budget = budget
        self.binding = binding
        self.source_digest = source_digest
        self.task_sha256 = _public().contract_digest(task)
        self.artifact_owner = context.artifact_owner
        self.receipts = []
        self.remaining_operations = task.budget.max_operations
        self.reserved_operations = 0
        self.local_refinement_calls = 0
        self.fallback_reason = None
        self.unresolved_answer = None
        self.unresolved_signature = "UNRESOLVED"
        self.neural_calls = 0
        self.ordered_cache = tuple(sorted(
            self.context.qualified_compositions,
            key=lambda item: (
                len(item.goal.expression_or_holes.nodes),
                item.qualification_receipt_sha256, item.goal.goal_id)))

    def evaluate(self, goal: _public().TaskGoal):

        try:
            evaluated = _public().execute_dag(
                goal, self.binding, memo=self.context.memo,
                operation_limit=min(self.remaining_operations, goal.budget.max_operations),
                artifact_owner=self.artifact_owner,
                support_task_sha256=self.task_sha256)
        except _public().BilqisError:
            # A failed executor has no cost receipt; reserve all remaining compute.
            self.reserved_operations += self.remaining_operations
            self.remaining_operations = 0
            raise
        self.remaining_operations -= evaluated.receipt.operation_count
        self.receipts.append(evaluated.receipt)
        return evaluated


    def decode(self, callback, *args):
        try:
            return callback(*args)
        except (_public().BilqisError, ValueError):
            # Decoder construction is an external typed-payload boundary.
            return None


    def result(self, answer: _public().TypedValue, route: _public().RouteKind, calls: int) -> _public().CapabilityResult:
        return _public().CapabilityResult(
            answer, route, tuple(self.receipts), calls,
            self.generation.generation_digest, self.source_digest,
            1.0 if route in (
                _public().RouteKind.EXACT, _public().RouteKind.CACHED_COMPOSITION,
                _public().RouteKind.DETERMINISTIC_FALLBACK) else None,
            self.task_sha256, self.binding.frontier.rights_epoch,
            self.binding.frontier.correction_generation, self.task.budget.max_operations,
            self.reserved_operations, self.local_refinement_calls, self.fallback_reason)


    def qualified(self, cached: _public().QualifiedComposition) -> bool:
        qualified = (
            cached.source_binding_digest == self.source_digest
            and cached.rights_epoch == self.binding.frontier.rights_epoch
            and cached.correction_generation
            == self.binding.frontier.correction_generation
            and self.context.qualification_verifier is not None
            and self.context.qualification_verifier(cached) is True
            and _public()._goal_allowed(cached.goal, self.task, self.budget))
        if qualified and self.artifact_owner is not None:
            self.artifact_owner.materialize_composition(
                cached, self.binding, self.task_sha256)
            self.artifact_owner.require_composition(
                cached, self.binding, self.task_sha256)
        return qualified


    def execute_proposal(self,
        proposal: _public().NeuralProposal | None, request: _public().NeuralRequest,
    ):
        if proposal is None:
            return None, "BAMF_C04_NEURAL_NO_PROPOSAL"
        if not isinstance(proposal, _public().NeuralProposal):
            return None, "BAMF_C04_NEURAL_PROPOSAL_INVALID"
        if (proposal.source_binding_digest != self.source_digest
                or proposal.generation_digest
                != self.generation.generation_digest
                or proposal.unresolved_signature
                != request.unresolved_signature
                or not _public()._goal_allowed(proposal.goal, self.task, self.budget)):
            return None, "BAMF_C04_NEURAL_PROPOSAL_SCOPE_DRIFT"
        try:
            evaluated = self.evaluate(proposal.goal)
        except _public().BilqisError:
            return None, "BAMF_C04_NEURAL_DAG_REJECTED"
        if evaluated.answer.state is not _public().ValueState.VALUE:
            return evaluated, "BAMF_C04_NEURAL_UNRESOLVED"
        return evaluated, None
