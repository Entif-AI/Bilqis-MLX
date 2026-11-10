"""Signer-free C07 v2 verification over A09, A02 and accepted B13 authority."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..factory.atlas_delta_scope import AtlasDeltaScopeHandoff
from .bamf_bundle import A02StagedVocabularyExtension
from .atlas_admission_policy import (
    AdmissionResult,
    AdmissionStatus,
    AtlasAdmissionContext,
)
from .atlas_lease_contracts import (
    AtlasAdmissionLease,
    AtlasAdmissionLeaseV2,
    _invalid,
)


@dataclass(frozen=True)
class AtlasAdmissionContextV2:
    legacy: AtlasAdmissionContext
    run_dir: Path

    def __post_init__(self):
        if (not isinstance(self.legacy, AtlasAdmissionContext)
                or not isinstance(self.run_dir, Path)):
            _invalid('BAMF_ATLAS_V2_CONTEXT_INVALID')


@dataclass(frozen=True)
class AtlasDeltaEnvelopeV2:
    handoff: AtlasDeltaScopeHandoff
    native_staged: A02StagedVocabularyExtension
    schema_version: str = 'bilqis.c07.atlas-delta-envelope/v2'

    def __post_init__(self):
        if (not isinstance(self.handoff, AtlasDeltaScopeHandoff)
                or not isinstance(self.native_staged, A02StagedVocabularyExtension)
                or self.schema_version != 'bilqis.c07.atlas-delta-envelope/v2'):
            _invalid('BAMF_ATLAS_V2_DELTA_INVALID')


@dataclass(frozen=True)
class AtlasDerivedAdmissionFactsV2:
    semantic_banks: int
    motif_pages: int
    total_atlas_semantic_identities: int
    checkpoint_bytes_lower_bound: int
    required_available_bytes_lower_bound: int
    new_semantic_identities: int

    def __post_init__(self):
        positive = (
            self.semantic_banks,
            self.motif_pages,
            self.total_atlas_semantic_identities,
            self.new_semantic_identities,
        )
        bounds = (
            self.checkpoint_bytes_lower_bound,
            self.required_available_bytes_lower_bound,
        )
        if (any(type(value) is not int or value < 1 for value in positive)
                or any(type(value) is not int or value < 0 for value in bounds)):
            _invalid('BAMF_ATLAS_V2_DERIVED_FACTS_INVALID')


def _staged(current, handoff, lease, reason, action):
    lease_sha256 = lease.digest() if isinstance(lease, AtlasAdmissionLeaseV2) else None
    return AdmissionResult(
        AdmissionStatus.STAGED,
        handoff.proposal.proposal_sha256,
        lease_sha256,
        current.legacy.current_release.release_sha256,
        handoff.staged_candidate.successor.release_sha256,
        reason,
        action,
    )


def _accepted_run_bindings(current: AtlasAdmissionContextV2, delta: AtlasDeltaEnvelopeV2):
    from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache
    from .atlas_admission import (
        _accepted_run_lease_identity,
        read_accepted_atlas_factory_release,
    )
    from .jit_adoption import _authenticate_native_staged_candidate

    legacy = current.legacy
    accepted_identity = _accepted_run_lease_identity(current.run_dir)
    accepted_release = read_accepted_atlas_factory_release(current.run_dir)
    try:
        cache = bind_accepted_execution_cache(current.run_dir)
    except (AttributeError, TypeError, ValueError):
        _invalid('BAMF_ATLAS_V2_ACCEPTED_RUN_DRIFT')
    if (legacy.run_identity != accepted_identity
            or legacy.current_release != accepted_release
            or delta.handoff.receipt.predecessor_release != accepted_release
            or delta.handoff.proposal.current_release_sha256
               != accepted_release.release_sha256
            or cache.source_authority_registry_sha256 is None
            or cache.source_authority_registry_sha256 != legacy.registry.digest):
        _invalid('BAMF_ATLAS_V2_ACCEPTED_RUN_DRIFT')
    _authenticate_native_staged_candidate(current.run_dir, delta.native_staged)


def _derive_v2_facts(delta: AtlasDeltaEnvelopeV2) -> AtlasDerivedAdmissionFactsV2:
    from bilqis_mlx.factory.candidate_realizations import realized_atlas_semantic_id
    from bilqis_mlx.runtime.bamf_bundle.vocabulary.admission_facts import (
        read_issued_a02_staged_admission_facts_v2,
    )

    handoff = delta.handoff
    a02 = read_issued_a02_staged_admission_facts_v2(delta.native_staged)
    try:
        expected_atlas_ids = tuple(
            realized_atlas_semantic_id(capability_id)
            for capability_id in handoff.receipt.selection.introduced_capability_ids)
    except ValueError:
        _invalid('BAMF_ATLAS_V2_A01_IDENTITY_AUTHORITY_UNAVAILABLE')
    selected = handoff.receipt.selection.selected_semantic_id
    if (expected_atlas_ids != a02.allocation_semantic_ids
            or selected not in expected_atlas_ids):
        _invalid('BAMF_ATLAS_V2_A02_IDENTITY_BINDING_DRIFT')
    return AtlasDerivedAdmissionFactsV2(
        semantic_banks=a02.semantic_banks,
        motif_pages=a02.motif_pages,
        total_atlas_semantic_identities=a02.total_atlas_semantic_identities,
        checkpoint_bytes_lower_bound=a02.checkpoint_bytes_lower_bound,
        required_available_bytes_lower_bound=a02.required_available_bytes_lower_bound,
        new_semantic_identities=len(a02.allocation_semantic_ids),
    )


def _replay_a09_proposal(current: AtlasAdmissionContextV2, handoff):
    from ..factory.jit_curriculum import propose_curriculum_delta

    legacy = current.legacy
    staged = handoff.staged_candidate
    staged.verify(legacy.frontier, legacy.current_release)
    deferred = tuple(sorted(
        item.candidate_id for item in handoff.candidate_frontier.candidates
        if item.candidate_id != staged.candidate_id))
    try:
        fresh = propose_curriculum_delta(
            legacy.frontier, legacy.current_release, legacy.ledger, legacy.plan,
            legacy.checkpoint.sha256, legacy.checkpoint.optimizer_step,
            candidate_bindings=(staged.binding,),
            deferred_candidate_ids=deferred)
    except (ValueError, TypeError, KeyError, AttributeError):
        _invalid('BAMF_ATLAS_V2_PROPOSAL_CONTEXT_DRIFT')
    if fresh != handoff.proposal:
        _invalid('BAMF_ATLAS_V2_PROPOSAL_CONTEXT_DRIFT')


def advance_atlas_frontier_v2(current, delta, lease):
    """Verify one v2 delta for C07; #958 itself never publishes B13 state."""
    if (not isinstance(current, AtlasAdmissionContextV2)
            or not isinstance(delta, AtlasDeltaEnvelopeV2)
            or (lease is not None
                and not isinstance(lease, (AtlasAdmissionLease, AtlasAdmissionLeaseV2)))):
        _invalid('BAMF_ATLAS_V2_ARGUMENT_INVALID')

    handoff = delta.handoff
    handoff.verify()
    _accepted_run_bindings(current, delta)

    legacy = current.legacy
    from .jit_adoption import verify_current_implementations
    _replay_a09_proposal(current, handoff)

    facts = _derive_v2_facts(delta)
    legacy.source_approval.verify_signature(legacy.registry)
    if not isinstance(lease, AtlasAdmissionLeaseV2):
        return _staged(
            current, handoff, lease, 'V2_ATLAS_LEASE_REQUIRED',
            'Request a separately human-authorized v2 Atlas lease; v1 resource '
            'semantics are never reinterpreted.')
    if lease.run_identity != legacy.run_identity:
        _invalid('BAMF_ATLAS_V2_LEASE_RUN_IDENTITY_DRIFT')
    lease.source_approval.verify_signature(legacy.registry)
    approval = legacy.source_approval
    if not approval.audit_passed or not approval.rights_compatible:
        return _staged(
            current, handoff, lease, 'SOURCE_OR_RIGHTS_HELD',
            'Reconcile the source-owned authority or rights hold; retain the staged successor.')
    if (approval != lease.source_approval
            or not set(handoff.family_ids) <= set(approval.source_family_ids)
            or not set(handoff.operator_ids) <= set(approval.operator_ids)):
        return _staged(
            current, handoff, lease, 'OUT_OF_LEASE_SCOPE',
            'Review the exact release, source rights, family/operator and policy scope '
            'before requesting a new v2 lease.')

    ceiling = lease.resource_ceiling
    if any(value > maximum for value, maximum in (
            (facts.semantic_banks, ceiling.max_semantic_banks),
            (facts.motif_pages, ceiling.max_motif_pages),
            (facts.total_atlas_semantic_identities,
             ceiling.max_total_atlas_semantic_identities),
            (facts.checkpoint_bytes_lower_bound,
             ceiling.max_checkpoint_bytes_lower_bound),
            (facts.required_available_bytes_lower_bound,
             ceiling.max_required_available_bytes_lower_bound))):
        return _staged(
            current, handoff, lease, 'RESOURCE_CEILING',
            'Retain the candidate; request v2 resource ceilings covering the exact '
            'A02-sealed lower bounds.')
    budget = approval.delta_budget_policy
    if (len(handoff.receipt.selection.introduced_capability_ids)
            > budget.max_capabilities
            or facts.new_semantic_identities > budget.max_new_semantic_identities):
        return _staged(
            current, handoff, lease, 'DELTA_BUDGET',
            'Split the qualified closure under its versioned per-delta admission budget.')

    from .atlas_production_admission import current_implementation_registries
    source_registry, answer_registry = current_implementation_registries(legacy)
    try:
        verify_current_implementations(
            handoff.staged_candidate.successor, source_registry, answer_registry)
    except (ValueError, TypeError, AttributeError) as error:
        reason = {
            'JIT_ADOPTION_SOURCE_IMPLEMENTATION_DRIFT':
                'BAMF_ATLAS_SOURCE_IMPLEMENTATION_DRIFT',
            'JIT_ADOPTION_ANSWER_IMPLEMENTATION_DRIFT':
                'BAMF_ATLAS_ANSWER_IMPLEMENTATION_DRIFT',
        }.get(str(error), 'BAMF_ATLAS_IMPLEMENTATION_REVALIDATION_FAILED')
        _invalid(reason)

    return _staged(
        current, handoff, lease, 'V2_DELTA_AUTHORITY_VERIFIED',
        'The signer-free A09/A02/B13 v2 authority is verified. Hand the exact '
        'artifacts to the C07 adoption owner; #958 performs no publication.')
