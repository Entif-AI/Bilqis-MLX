"""Owner-derived A09/Factory scope for one staged C07 delta handoff."""
from __future__ import annotations

from dataclasses import dataclass, fields
import hashlib

from bilqis_mlx.source_adapters.formal_identity import (
    OperatorDispositionKind,
    source_operator_disposition,
)

from .atlas_frontier_contracts import _bytes, _fail
from .atlas_frontier_progress_contracts import StagedSelectionReceipt
from .candidate_frontier import CandidateFrontierRelease
from .candidate_staging import StagedCandidate
from .executable_release import ExecutableFactoryRelease
from .jit_curriculum import CurriculumDeltaProposal, ProposalDisposition


HANDOFF_SCHEMA = "bilqis.factory-atlas-delta-scope-handoff/v1"


@dataclass(frozen=True)
class CapabilityOperatorScope:
    capability_id: str
    source_adapter_id: str
    disposition: OperatorDispositionKind
    operator_id: str | None
    semantic_root: str | None
    provider_implementation_sha256: str
    generator_id: str
    oracle_id: str

    def __post_init__(self) -> None:
        operator = self.disposition is OperatorDispositionKind.OPERATOR
        if (not all(isinstance(value, str) and value for value in (
                self.capability_id, self.source_adapter_id,
                self.provider_implementation_sha256, self.generator_id,
                self.oracle_id))
                or not isinstance(self.disposition, OperatorDispositionKind)
                or operator != (self.operator_id is not None)
                or operator != (self.semantic_root is not None)
                or (self.operator_id is not None
                    and (not isinstance(self.operator_id, str) or not self.operator_id))
                or (self.semantic_root is not None
                    and (not isinstance(self.semantic_root, str) or not self.semantic_root))):
            _fail("BAMF_ATLAS_DELTA_OPERATOR_SCOPE_INVALID")


def resolve_v2_operator_scopes(
        release: ExecutableFactoryRelease,
        capability_ids: tuple[str, ...]) -> tuple[CapabilityOperatorScope, ...]:
    """Replay source-owned operator disposition against exact v2 release facts."""
    if (type(release) is not ExecutableFactoryRelease
            or type(capability_ids) is not tuple
            or not capability_ids
            or len(capability_ids) != len(set(capability_ids))
            or any(not isinstance(item, str) or not item for item in capability_ids)):
        _fail("BAMF_ATLAS_DELTA_OPERATOR_SCOPE_INPUT_INVALID")
    release.verify()
    executions = release.execution_plan.capability_map
    bindings = release.source_bindings.by_capability
    adapters = {item.adapter_id: item for item in release.source_adapters}
    if len(adapters) != len(release.source_adapters):
        _fail("BAMF_ATLAS_DELTA_OPERATOR_SCOPE_PROVIDER_INVALID")

    result = []
    for capability_id in capability_ids:
        execution = executions.get(capability_id)
        binding = bindings.get(capability_id)
        if execution is None or binding is None:
            _fail("BAMF_ATLAS_DELTA_OPERATOR_SCOPE_CAPABILITY_MISSING")
        descriptor = adapters.get(execution.provider_id)
        authority = source_operator_disposition(capability_id, execution.provider_id)
        if descriptor is None or authority is None:
            _fail("BAMF_ATLAS_DELTA_OPERATOR_SCOPE_UNSUPPORTED")
        if (authority.source_adapter_id != descriptor.adapter_id
                or authority.generator_id != descriptor.generator_id
                or authority.accepted_oracle_ids != descriptor.accepted_oracle_ids
                or authority.implementation_sha256 != descriptor.implementation_sha256
                or execution.provider_implementation_sha256
                   != descriptor.implementation_sha256
                or execution.oracle_id != binding.oracle_id
                or execution.oracle_id not in descriptor.accepted_oracle_ids
                or binding.generator_id != descriptor.generator_id
                or execution.source_anchor != binding.source_anchor):
            _fail("BAMF_ATLAS_DELTA_OPERATOR_SCOPE_AUTHORITY_DRIFT")
        result.append(CapabilityOperatorScope(
            capability_id=capability_id,
            source_adapter_id=descriptor.adapter_id,
            disposition=authority.kind,
            operator_id=authority.operator_id,
            semantic_root=authority.semantic_root,
            provider_implementation_sha256=descriptor.implementation_sha256,
            generator_id=descriptor.generator_id,
            oracle_id=execution.oracle_id,
        ))
    return tuple(result)


@dataclass(frozen=True)
class AtlasDeltaScopeHandoff:
    candidate_frontier: CandidateFrontierRelease
    receipt: StagedSelectionReceipt
    staged_candidate: StagedCandidate
    proposal: CurriculumDeltaProposal
    family_ids: tuple[str, ...]
    operator_scopes: tuple[CapabilityOperatorScope, ...]
    handoff_sha256: str
    schema: str = HANDOFF_SCHEMA

    @property
    def operator_ids(self) -> tuple[str, ...]:
        return tuple(sorted({
            scope.operator_id for scope in self.operator_scopes
            if scope.disposition is OperatorDispositionKind.OPERATOR
            and scope.operator_id is not None
        }))

    def expected_digest(self) -> str:
        return hashlib.sha256(_bytes({
            field.name: getattr(self, field.name)
            for field in fields(self) if field.name != "handoff_sha256"
        })).hexdigest()

    def verify(self) -> None:
        if (self.schema != HANDOFF_SCHEMA
                or type(self.candidate_frontier) is not CandidateFrontierRelease
                or type(self.receipt) is not StagedSelectionReceipt
                or type(self.staged_candidate) is not StagedCandidate
                or type(self.proposal) is not CurriculumDeltaProposal
                or type(self.family_ids) is not tuple
                or not self.family_ids
                or self.family_ids != tuple(sorted(set(self.family_ids)))
                or type(self.operator_scopes) is not tuple
                or not self.operator_scopes):
            _fail("BAMF_ATLAS_DELTA_SCOPE_HANDOFF_INVALID")
        self.candidate_frontier.verify()
        self.receipt.verify()
        self.proposal.verify()
        staged = self.staged_candidate
        try:
            staged.verify(
                self.candidate_frontier,
                self.receipt.predecessor_release,
            )
        except (TypeError, ValueError):
            _fail("BAMF_ATLAS_DELTA_SCOPE_STAGED_CANDIDATE_DRIFT")
        selection = self.receipt.selection
        successor = self.receipt.staged_successor
        expected_families = tuple(sorted({
            item.family_id for item in selection.selected_obligations
        }))
        expected_scopes = resolve_v2_operator_scopes(
            successor, selection.introduced_capability_ids)
        if (staged.successor != successor
                or self.candidate_frontier.release_sha256
                   != self.proposal.frontier_sha256
                or staged.frontier_sha256 != self.proposal.frontier_sha256
                or self.proposal.disposition is not ProposalDisposition.PROPOSAL
                or self.proposal.current_release_sha256
                   != self.receipt.predecessor_release.release_sha256
                or self.proposal.selected_candidate_ids != (staged.candidate_id,)
                or self.proposal.selected_successor_sha256 != successor.release_sha256
                or selection.introduced_capability_ids
                   != successor.transition.added_capabilities
                or staged.target_capability_id
                   not in selection.introduced_capability_ids
                or self.family_ids != expected_families
                or self.operator_scopes != expected_scopes
                or self.handoff_sha256 != self.expected_digest()):
            _fail("BAMF_ATLAS_DELTA_SCOPE_HANDOFF_DRIFT")


def build_atlas_delta_scope_handoff(
        candidate_frontier: CandidateFrontierRelease,
        receipt: StagedSelectionReceipt,
        staged_candidate: StagedCandidate,
        proposal: CurriculumDeltaProposal) -> AtlasDeltaScopeHandoff:
    """Bind existing A09 selection and Factory v2 authority without a signer."""
    if (type(candidate_frontier) is not CandidateFrontierRelease
            or type(receipt) is not StagedSelectionReceipt):
        _fail("BAMF_ATLAS_DELTA_SCOPE_RECEIPT_REQUIRED")
    families = tuple(sorted({
        item.family_id for item in receipt.selection.selected_obligations
    }))
    scopes = resolve_v2_operator_scopes(
        receipt.staged_successor, receipt.selection.introduced_capability_ids)
    provisional = AtlasDeltaScopeHandoff(
        candidate_frontier, receipt, staged_candidate, proposal,
        families, scopes, "0" * 64)
    handoff = AtlasDeltaScopeHandoff(
        candidate_frontier, receipt, staged_candidate, proposal, families, scopes,
        provisional.expected_digest())
    handoff.verify()
    return handoff
