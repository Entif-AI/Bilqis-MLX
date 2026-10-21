"""Revalidate a selected JIT proposal before the normal admission transaction."""
from ..factory.jit_curriculum import ProposalDisposition, propose_curriculum_delta


def resolve_ready_candidate(frontier, current, ledger, plan, checkpoint, proposal, staged):
    proposal.verify()
    if proposal.disposition is not ProposalDisposition.PROPOSAL:
        raise ValueError("JIT_ADOPTION_READY_PROPOSAL_REQUIRED")
    for item in staged:
        item.verify(frontier, current)
    fresh = propose_curriculum_delta(frontier, current, ledger, plan,
        checkpoint.sha256, checkpoint.optimizer_step,
        candidate_bindings=tuple(item.binding for item in staged))
    if fresh != proposal:
        raise ValueError("JIT_ADOPTION_PROPOSAL_CONTEXT_CHANGED")
    matches = tuple(item for item in staged if
        (item.candidate_id,) == proposal.selected_candidate_ids and
        item.successor.release_sha256 == proposal.selected_successor_sha256)
    if len(matches) != 1:
        raise ValueError("JIT_ADOPTION_EXACT_SUCCESSOR_REQUIRED")
    return matches[0]


def verify_current_implementations(successor, source_registry, answer_registry):
    """A sealed historical package cannot authorize changed provider code."""
    sources = {item.adapter_id: item for item in successor.source_adapters}
    for execution in successor.execution_plan.capabilities:
        binding = successor.source_bindings.by_capability[execution.capability_id]
        actual = source_registry.require(binding.generator_id, binding.oracle_id).descriptor
        if actual != sources.get(execution.provider_id):
            raise ValueError("JIT_ADOPTION_SOURCE_IMPLEMENTATION_DRIFT")
    if tuple(answer_registry.require(item.kind).descriptor
             for item in successor.answer_modalities) != successor.answer_modalities:
        raise ValueError("JIT_ADOPTION_ANSWER_IMPLEMENTATION_DRIFT")
