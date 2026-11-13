"""C-owned projections of frozen A09/A12 obligations onto native staged work."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
import re

from ..factory.candidate_staging import StagedCandidate
from ..factory.jit_curriculum import CurriculumDeltaProposal
from ..learning.champions import Checkpoint
from ..semantics.cognitive_dependencies import DependencyKind, DependencyRef
from ..semantics.domains import contract_digest
from .atlas_admission import (AtlasAdmissionLease, AtlasSourceApproval, LeaseRunIdentity,
                              _invalid, _name, _names, _sha)
from .atlas_production_admission import (
    PostAdmissionTotals, current_implementation_registries,
    native_post_admission_totals, require_accepted_delta_registry,
    require_native_semantic_binding,
)
from .atlas_revalidation import SourceAuthorityRegistry
from .jit_adoption import resolve_ready_candidate, verify_current_implementations


@dataclass(frozen=True)
class AtlasAdmissionContext:
    run_identity: LeaseRunIdentity
    current_release: object
    frontier: object
    ledger: object
    plan: object
    checkpoint: Checkpoint
    source_approval: AtlasSourceApproval
    registry: SourceAuthorityRegistry
    source_registry: object | None = None
    answer_registry: object | None = None
    runtime: object | None = None
    native_staged: object | None = None
    source_authority: object | None = None

    def __post_init__(self):
        # These three values are an inseparable production handoff, not new
        # authorization.  The native executor independently replays accepted
        # B13 custody, the persisted lease, the opaque C09 source authority and
        # the owner-issued A02 staged extension before it can publish anything.
        production = (self.runtime, self.native_staged, self.source_authority)
        if (not isinstance(self.run_identity, LeaseRunIdentity) or not isinstance(self.checkpoint, Checkpoint)
                or not isinstance(self.source_approval, AtlasSourceApproval)
                or not isinstance(self.registry, SourceAuthorityRegistry)
                or (self.source_registry is None) != (self.answer_registry is None)
                or (any(value is not None for value in production)
                    and any(value is None for value in production))):
            _invalid('BAMF_ATLAS_ADMISSION_CONTEXT_INVALID')


@dataclass(frozen=True)
class AtlasDeltaEnvelope:
    proposal: CurriculumDeltaProposal
    staged: StagedCandidate
    source_family_ids: tuple[str, ...]
    operator_ids: tuple[str, ...]
    post_admission_totals: PostAdmissionTotals
    new_semantic_identities: int
    source_approval_digest: str
    source_owner: str
    signature_hex: str
    verification_mode: str = field(default='DISPOSABLE_CONTRACT', init=False)
    schema_version: str = field(default='bilqis.c07.atlas-delta-envelope/v1', init=False)

    def __post_init__(self):
        if (not isinstance(self.proposal, CurriculumDeltaProposal) or not isinstance(self.staged, StagedCandidate)
                or not _names(self.source_family_ids) or not _names(self.operator_ids, allow_empty=True)
                or not isinstance(self.post_admission_totals, PostAdmissionTotals)
                or type(self.new_semantic_identities) is not int or self.new_semantic_identities < 0
                or not _sha(self.source_approval_digest) or not _name(self.source_owner)
                or not isinstance(self.signature_hex, str)
                or re.fullmatch('[0-9a-f]{128}', self.signature_hex) is None):
            _invalid('BAMF_ATLAS_DELTA_ENVELOPE_INVALID')

    def signing_bytes(self):
        return json.dumps({'schema': self.schema_version, 'verification_mode': self.verification_mode,
            'proposal_sha256': self.proposal.proposal_sha256, 'staged_sha256': self.staged.staged_sha256,
            'source_family_ids': self.source_family_ids, 'operator_ids': self.operator_ids,
            'post_admission_totals': asdict(self.post_admission_totals),
            'new_semantic_identities': self.new_semantic_identities,
            'source_approval_digest': self.source_approval_digest, 'source_owner': self.source_owner},
            sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


class AdmissionStatus(str, Enum):
    STAGED = 'STAGED'
    ADOPTED = 'ADOPTED'


@dataclass(frozen=True)
class AdmissionResult:
    status: AdmissionStatus
    proposal_sha256: str
    lease_sha256: str | None
    retained_release_sha256: str
    staged_successor_sha256: str
    reason: str
    operator_action: str
    state_adopted: bool = False
    requires_cold_resume: bool = False
    accepted_generation: int | None = None
    accepted_manifest_sha256: str | None = None
    actual_neural_updates: int = field(default=0, init=False)
    schema_version: str = field(default='bilqis.c07.atlas-admission-result/v2', init=False)

    def __post_init__(self):
        adopted = self.status is AdmissionStatus.ADOPTED
        if (adopted != self.state_adopted
                or adopted != self.requires_cold_resume
                or self.actual_neural_updates != 0
                or (adopted and (
                    type(self.accepted_generation) is not int
                    or self.accepted_generation < 0
                    or not _sha(self.accepted_manifest_sha256)))
                or (not adopted and (
                    self.accepted_generation is not None
                    or self.accepted_manifest_sha256 is not None))):
            _invalid('BAMF_ATLAS_ADMISSION_RESULT_INVALID')


def advance_atlas_frontier(current, proposal, lease):
    if (not isinstance(current, AtlasAdmissionContext) or not isinstance(proposal, AtlasDeltaEnvelope)
            or (lease is not None and not isinstance(lease, AtlasAdmissionLease))):
        _invalid('BAMF_ATLAS_ADMISSION_ARGUMENT_INVALID')
    require_accepted_delta_registry(current)
    current.source_approval.verify_signature(current.registry)
    current.registry.verify_detached(proposal.source_owner,
        DependencyRef(DependencyKind.ARTIFACT, 'atlas-delta:' + proposal.proposal.proposal_sha256),
        proposal.signature_hex, proposal.signing_bytes())
    try:
        resolved = resolve_ready_candidate(current.frontier, current.current_release, current.ledger,
            current.plan, current.checkpoint, proposal.proposal, (proposal.staged,))
        if resolved != proposal.staged:
            _invalid('BAMF_ATLAS_EXACT_STAGED_SUCCESSOR_REQUIRED')
    except (ValueError, TypeError, KeyError, AttributeError):
        _invalid('BAMF_ATLAS_NATIVE_PROPOSAL_CONTEXT_DRIFT')
    def staged(reason, action):
        return AdmissionResult(AdmissionStatus.STAGED, proposal.proposal.proposal_sha256,
            lease.digest() if lease is not None else None, current.current_release.release_sha256,
            proposal.staged.successor.release_sha256, reason, action)
    if lease is None:
        return staged('EXPLICIT_ATLAS_LEASE_REQUIRED', 'Select an exact approved scope through a human-started Atlas admission request.')
    if lease.run_identity != current.run_identity:
        _invalid('BAMF_ATLAS_LEASE_RUN_IDENTITY_DRIFT')
    lease.source_approval.verify(current.registry)
    approval = current.source_approval
    if not approval.audit_passed or not approval.rights_compatible:
        return staged('SOURCE_OR_RIGHTS_HELD', 'Reconcile the source-owned authority or rights hold; retain the staged successor.')
    if (approval != lease.source_approval
            or not set(proposal.source_family_ids) <= set(approval.source_family_ids)
            or not set(proposal.operator_ids) <= set(approval.operator_ids)):
        return staged('OUT_OF_LEASE_SCOPE', 'Review the exact release, source rights, family/operator and policy scope before requesting a new lease.')
    if proposal.source_approval_digest != contract_digest(approval):
        _invalid('BAMF_ATLAS_DELTA_APPROVAL_BINDING_DRIFT')
    native_staged = None
    if current.runtime is not None:
        native_staged = require_native_semantic_binding(current, proposal)
        owner_totals = native_post_admission_totals(native_staged)
        if proposal.post_admission_totals != owner_totals:
            _invalid('BAMF_ATLAS_POST_ADMISSION_TOTALS_DRIFT')
    totals, ceiling = proposal.post_admission_totals, lease.resource_ceiling
    if any(value > maximum for value, maximum in (
            (totals.semantic_banks, ceiling.max_semantic_banks), (totals.motif_pages, ceiling.max_motif_pages),
            (totals.total_semantic_identities, ceiling.max_total_semantic_identities),
            (totals.memory_bytes, ceiling.max_memory_bytes), (totals.disk_bytes, ceiling.max_disk_bytes))):
        return staged('RESOURCE_CEILING', 'Retain the candidate; select an explicit resource ceiling that covers post-admission totals.')
    budget = approval.delta_budget_policy
    if (len(proposal.staged.successor.transition.added_capabilities) > budget.max_capabilities
            or proposal.new_semantic_identities > budget.max_new_semantic_identities):
        return staged('DELTA_BUDGET', 'Split the qualified closure under its versioned per-delta admission budget.')
    source_registry, answer_registry = current_implementation_registries(current)
    try:
        verify_current_implementations(
            proposal.staged.successor, source_registry, answer_registry)
    except (ValueError, TypeError, AttributeError) as error:
        reason = {
            'JIT_ADOPTION_SOURCE_IMPLEMENTATION_DRIFT': 'BAMF_ATLAS_SOURCE_IMPLEMENTATION_DRIFT',
            'JIT_ADOPTION_ANSWER_IMPLEMENTATION_DRIFT': 'BAMF_ATLAS_ANSWER_IMPLEMENTATION_DRIFT',
        }.get(str(error), 'BAMF_ATLAS_IMPLEMENTATION_REVALIDATION_FAILED')
        _invalid(reason)
    if current.runtime is None:
        return staged(
            'ACCEPTED_RUN_AUTHORITY_UNAVAILABLE',
            'Keep this exact successor staged until the accepted run owner binds the persisted lease to production custody.')

    from .jit_adoption import _execute_prepared_successor_adoption
    adopted = _execute_prepared_successor_adoption(
        current.runtime, frontier=current.frontier, current=current.current_release,
        ledger=current.ledger, plan=current.plan, checkpoint=current.checkpoint,
        proposal=proposal.proposal, staged=(proposal.staged,),
        source_registry=source_registry, answer_registry=answer_registry,
        native_staged=native_staged, atlas_lease=lease,
        source_authority=current.source_authority)
    if adopted.native_pointer is None:
        _invalid('BAMF_ATLAS_ACCEPTED_GENERATION_REQUIRED')
    return AdmissionResult(
        AdmissionStatus.ADOPTED, proposal.proposal.proposal_sha256, lease.digest(),
        proposal.staged.successor.release_sha256,
        proposal.staged.successor.release_sha256, 'ADOPTED',
        'Cold-resume from accepted B13 custody before further neural work.', True,
        True, adopted.native_pointer.get('generation'),
        adopted.native_pointer.get('manifest_sha256'))
