"""Proposal-only JIT selection over already verified executable releases."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json

from .autonomy import evidence_complete_capabilities
from .candidate_frontier import CandidateFrontierRelease
from .executable_release import ExecutableFactoryRelease


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode()).hexdigest()


def _sha(value: str, code: str) -> str:
    if (not isinstance(value, str) or len(value) != 64 or
            any(char not in "0123456789abcdef" for char in value)):
        raise ValueError(code)
    return value


class ProposalDisposition(str, Enum):
    PROPOSAL = "PROPOSAL"
    SOURCE_DEVELOPMENT = "SOURCE_DEVELOPMENT"


@dataclass(frozen=True)
class CandidateBinding:
    """An exact candidate-to-precompiled-successor binding, never an admission."""

    candidate_id: str
    target_capability_id: str
    source_sense_id: str
    source_anchor: str
    staged_successor: ExecutableFactoryRelease

    def __post_init__(self) -> None:
        if (not all(isinstance(value, str) and value for value in (
                self.candidate_id, self.target_capability_id,
                self.source_sense_id, self.source_anchor)) or
                not isinstance(self.staged_successor, ExecutableFactoryRelease)):
            raise ValueError("JIT_CANDIDATE_BINDING_INVALID")


@dataclass(frozen=True)
class CandidateGateResult:
    candidate_id: str
    eligible: bool
    required_source_work: tuple[str, ...]
    rationale: tuple[str, ...]
    operation_cost: tuple[int, int, int, int]


@dataclass(frozen=True)
class CurriculumDeltaProposal:
    disposition: ProposalDisposition
    frontier_sha256: str
    current_release_sha256: str
    autonomy_plan_sha256: str
    checkpoint_sha256: str
    optimizer_step: int
    evidence_digest: str
    current_mastery: tuple[str, ...]
    selected_candidate_ids: tuple[str, ...]
    selected_successor_sha256: str | None
    intended_profile_id: str | None
    abi_geometry: str | None
    candidate_gates: tuple[CandidateGateResult, ...]
    deferred_candidate_ids: tuple[str, ...]
    proposal_sha256: str

    def __post_init__(self) -> None:
        if (not isinstance(self.disposition, ProposalDisposition) or
                type(self.optimizer_step) is not int or self.optimizer_step < 0 or
                len(set(self.selected_candidate_ids)) != len(self.selected_candidate_ids) or
                len(set(self.deferred_candidate_ids)) != len(self.deferred_candidate_ids) or
                any(not isinstance(item, CandidateGateResult)
                    for item in self.candidate_gates)):
            raise ValueError("JIT_CURRICULUM_PROPOSAL_INVALID")
        for value in (self.frontier_sha256, self.current_release_sha256,
                      self.autonomy_plan_sha256, self.checkpoint_sha256,
                      self.evidence_digest, self.proposal_sha256):
            _sha(value, "JIT_CURRICULUM_PROPOSAL_DIGEST_INVALID")
        if self.selected_successor_sha256 is not None:
            _sha(self.selected_successor_sha256,
                 "JIT_CURRICULUM_PROPOSAL_SUCCESSOR_INVALID")
        if self.disposition is ProposalDisposition.PROPOSAL:
            if (not self.selected_candidate_ids or not self.selected_successor_sha256 or
                    not self.intended_profile_id or not self.abi_geometry):
                raise ValueError("JIT_CURRICULUM_PROPOSAL_SELECTION_INVALID")
        elif self.selected_candidate_ids or self.selected_successor_sha256 is not None:
            raise ValueError("JIT_CURRICULUM_SOURCE_DEVELOPMENT_INVALID")

    def manifest(self) -> dict:
        return {**asdict(self), "disposition": self.disposition.value,
                "proposal_sha256": None}

    def expected_digest(self) -> str:
        return _digest(self.manifest())

    def verify(self) -> None:
        if self.proposal_sha256 != self.expected_digest():
            raise ValueError("JIT_CURRICULUM_PROPOSAL_DIGEST_MISMATCH")


def _cost(current: ExecutableFactoryRelease, successor: ExecutableFactoryRelease,
          target: str) -> tuple[int, int, int, int]:
    current_plan, next_plan = current.execution_plan, successor.execution_plan
    current_ids = set(item.capability_id for item in current_plan.capabilities)
    next_ids = set(item.capability_id for item in next_plan.capabilities)
    new = next_ids - current_ids
    kinds = {family.kind for item in current_plan.capabilities for family in item.answer_families}
    next_kinds = {family.kind for item in next_plan.capabilities for family in item.answer_families}
    providers = {item.provider_id for item in current_plan.capabilities}
    next_providers = {item.provider_id for item in next_plan.capabilities}
    target_execution = next_plan.capability_map[target]
    return (len(new), len(next_kinds - kinds), len(next_providers - providers),
            len(target_execution.prerequisites) + len(target_execution.composed_of))


def _candidate_by_id(frontier: CandidateFrontierRelease) -> dict:
    return {item.candidate_id: item for item in frontier.candidates}


def _gate(frontier, candidate, binding, current, mastered) -> CandidateGateResult:
    debt: list[str] = []
    rationale: list[str] = []
    if binding is None:
        debt.append("STAGED_SUCCESSOR_BINDING_REQUIRED")
        return CandidateGateResult(candidate.candidate_id, False, tuple(debt),
                                   ("no exact executable binding",), (9999,) * 4)
    try:
        binding.staged_successor.verify_successor_of(current)
    except (TypeError, ValueError):
        debt.append("VERIFIED_SUCCESSOR_REQUIRED")
    successor = binding.staged_successor
    transition = successor.transition
    if (transition is None or
            transition.added_capabilities != (binding.target_capability_id,) or
            transition.removed_capabilities or transition.changed_capabilities or
            transition.removed_grades):
        debt.append("SUCCESSOR_DELTA_SCOPE_MISMATCH")
    target = successor.execution_plan.capability_map.get(binding.target_capability_id)
    source = successor.source_bindings.by_capability.get(binding.target_capability_id)
    senses = {item.sense_id: item for item in frontier.senses}
    sense = senses.get(candidate.target_sense_id)
    if binding.target_capability_id != candidate.proposed_capability_id:
        debt.append("TARGET_CAPABILITY_CANDIDATE_MISMATCH")
    if binding.source_sense_id != candidate.target_sense_id or sense is None:
        debt.append("EXACT_SOURCE_SENSE_BINDING_REQUIRED")
    if (target is None or source is None or target.source_anchor != binding.source_anchor or
            source.source_anchor != binding.source_anchor):
        debt.append("EXECUTABLE_SOURCE_ANCHOR_REQUIRED")
    if binding.target_capability_id in current.execution_plan.capability_map:
        debt.append("NEW_CAPABILITY_REQUIRED")
    if target is not None:
        explicit = set(target.prerequisites) | set(target.composed_of)
        missing_hypotheses = {edge.capability_id for edge in candidate.prerequisites} - explicit
        if missing_hypotheses:
            debt.append("HYPOTHESIS_EDGE_REQUIRES_EXECUTABLE_ACCOUNTING")
        missing_current = explicit - set(mastered)
        if missing_current:
            debt.append("CURRENT_PREREQUISITE_EVIDENCE_REQUIRED")
            rationale.append("missing=" + ",".join(sorted(missing_current)))
    if not debt:
        rationale.append("verified successor and current checkpoint evidence")
    return CandidateGateResult(candidate.candidate_id, not debt, tuple(debt), tuple(rationale),
                               _cost(current, successor, binding.target_capability_id)
                               if target is not None else (9999,) * 4)


def propose_curriculum_delta(
    frontier: CandidateFrontierRelease, current_release: ExecutableFactoryRelease,
    ledger, plan, checkpoint_sha256: str, optimizer_step: int, *,
    candidate_bindings: tuple[CandidateBinding, ...] = (),
    deferred_candidate_ids: tuple[str, ...] = (),
) -> CurriculumDeltaProposal:
    """Select a legal thin slice; this function never calls an admission API."""
    if not isinstance(frontier, CandidateFrontierRelease) or not isinstance(
            current_release, ExecutableFactoryRelease):
        raise TypeError("JIT_CURRICULUM_INPUT_INVALID")
    frontier.verify()
    current_release.verify()
    _sha(checkpoint_sha256, "JIT_CURRICULUM_CHECKPOINT_INVALID")
    if type(optimizer_step) is not int or optimizer_step < 0:
        raise ValueError("JIT_CURRICULUM_STEP_INVALID")
    if (len(set(deferred_candidate_ids)) != len(deferred_candidate_ids) or
            any(item not in _candidate_by_id(frontier) for item in deferred_candidate_ids)):
        raise ValueError("JIT_CURRICULUM_DEFERRED_INVALID")
    bindings = {item.candidate_id: item for item in candidate_bindings}
    if (len(bindings) != len(candidate_bindings) or
            any(item.candidate_id not in _candidate_by_id(frontier)
                for item in candidate_bindings)):
        raise ValueError("JIT_CURRICULUM_BINDING_INVALID")
    mastered = evidence_complete_capabilities(
        current_release, ledger, plan=plan,
        current_checkpoint_sha256=checkpoint_sha256,
        current_optimizer_step=optimizer_step)
    candidates = _candidate_by_id(frontier)
    gates = tuple(_gate(frontier, candidate, bindings.get(candidate.candidate_id),
                        current_release, mastered)
                  for candidate in frontier.candidates
                  if candidate.candidate_id not in deferred_candidate_ids)
    eligible = [gate for gate in gates if gate.eligible]
    evidence_digest = _digest({"ledger": asdict(ledger), "mastery": mastered,
                               "checkpoint": checkpoint_sha256, "step": optimizer_step})
    common = dict(frontier_sha256=frontier.release_sha256,
                  current_release_sha256=current_release.release_sha256,
                  autonomy_plan_sha256=plan.digest(), checkpoint_sha256=checkpoint_sha256,
                  optimizer_step=optimizer_step, evidence_digest=evidence_digest,
                  current_mastery=mastered, candidate_gates=gates,
                  deferred_candidate_ids=deferred_candidate_ids)
    if not eligible:
        proposal = CurriculumDeltaProposal(ProposalDisposition.SOURCE_DEVELOPMENT,
            selected_candidate_ids=(), selected_successor_sha256=None,
            intended_profile_id=None, abi_geometry=None, proposal_sha256="0" * 64,
            **common)
    else:
        winner = min(eligible, key=lambda item: (item.operation_cost, item.candidate_id))
        successor = bindings[winner.candidate_id].staged_successor
        proposal = CurriculumDeltaProposal(ProposalDisposition.PROPOSAL,
            selected_candidate_ids=(winner.candidate_id,),
            selected_successor_sha256=successor.release_sha256,
            intended_profile_id=successor.profile.profile_id,
            abi_geometry=successor.transition.semantic_geometry,
            proposal_sha256="0" * 64, **common)
    proposal = CurriculumDeltaProposal(**{**asdict(proposal),
        "disposition": proposal.disposition,
        "candidate_gates": proposal.candidate_gates,
        "proposal_sha256": proposal.expected_digest()})
    proposal.verify()
    return proposal
