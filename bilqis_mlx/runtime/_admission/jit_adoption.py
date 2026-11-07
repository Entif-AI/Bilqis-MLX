"""Revalidate and commit a selected JIT proposal through the native transaction.

This module does not issue Atlas-admission authority.  The public C07 policy owns
lease/source checks; this owner only removes the old executor gap after those
checks have succeeded.  In particular, the provisional ``DISPOSABLE_CONTRACT``
lease cannot reach this executor through ``advance_atlas_frontier``.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

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


@dataclass(frozen=True)
class _PreparedSuccessorRuntime:
    """The one mutable learner lane as immutable executor inputs.

    Constructing this record grants no admission authority.  Every execution
    re-reads the admitted Factory release and school checkpoint from ``receipt``
    immediately before entering the existing prepared-successor transaction.
    """

    mx: object
    run_dir: Path
    receipt: dict
    grade_a_course: object
    source_root: Path | None
    graph: dict
    parameters: object
    optimizer: object
    reserve_gib: float

    def __post_init__(self):
        if (not isinstance(self.run_dir, Path) or not isinstance(self.receipt, dict)
                or not isinstance(self.graph, dict)
                or not isinstance(self.reserve_gib, (int, float))
                or self.reserve_gib < 0):
            raise ValueError("JIT_ADOPTION_EXECUTOR_CONTEXT_INVALID")


def _execute_prepared_successor_adoption(
        runtime: _PreparedSuccessorRuntime, *, frontier, current, ledger, plan,
        checkpoint, proposal, staged, source_registry, answer_registry):
    """Freshly revalidate then enter the existing atomic prepared-successor owner.

    This is deliberately a concrete owner, not a caller callback.  It cannot
    create a lease, reinterpret a source approval, or claim that a disposable
    C07 contract is production run authority.
    """
    if not isinstance(runtime, _PreparedSuccessorRuntime):
        raise ValueError("JIT_ADOPTION_EXECUTOR_RUNTIME_INVALID")
    selected = resolve_ready_candidate(
        frontier, current, ledger, plan, checkpoint, proposal, staged)
    verify_current_implementations(
        selected.successor, source_registry, answer_registry)

    from . import admission as runtime_admission
    from . import release_adoption, state as runtime_state
    from ..factory.schedule import schedule_program_from_executable_release

    admitted = runtime_admission._require_executable_factory_admission(
        runtime.run_dir, runtime.receipt, runtime.graph)
    program = schedule_program_from_executable_release(admitted)
    school = runtime_state._state_from_json(runtime.receipt["school"], program)
    if (admitted.release_sha256 != current.release_sha256
            or school.current_student != checkpoint):
        raise ValueError("JIT_ADOPTION_RUNTIME_CONTEXT_CHANGED")

    parameters, optimizer, graph, receipt, course = (
        release_adoption._adopt_prepared_successor(
            runtime.mx, runtime.run_dir, runtime.receipt,
            runtime.grade_a_course, runtime.source_root, runtime.graph,
            runtime.parameters, runtime.optimizer, selected,
            reserve_gib=float(runtime.reserve_gib)))
    return replace(
        runtime, receipt=receipt, grade_a_course=course, graph=graph,
        parameters=parameters, optimizer=optimizer)
