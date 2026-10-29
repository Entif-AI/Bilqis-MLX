"""C07 lease contracts and disposable persistence, pending accepted run authority.

These C-owned boundary records do not implement A09, A12 or B13. Their explicit
contract-fixture provenance cannot authorize a saved human learner.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re

from ..errors import ErrorBus, SCHOOL
from ..learning.champions import Checkpoint
from ..semantics.cognitive_dependencies import DependencyKind, DependencyRef
from ..semantics.domains import contract_digest
from .atlas_revalidation import SourceAuthorityRegistry
from .state import _durable_json


def _invalid(reason):
    ErrorBus.raise_(SCHOOL.BAMF_ATLAS_ADMISSION.INVALID, reason=reason)


def _sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _name(value):
    return isinstance(value, str) and bool(value)


def _names(values, *, allow_empty=False):
    return (isinstance(values, tuple) and (allow_empty or bool(values)) and all(_name(value) for value in values)
            and values == tuple(sorted(set(values))))


@dataclass(frozen=True)
class LeaseRunIdentity:
    lineage_id: str
    initial_generation_digest: str
    topology_digest: str
    origin_checkpoint: Checkpoint
    verification_mode: str = field(default='DISPOSABLE_CONTRACT', init=False)
    schema_version: str = field(default='bilqis.c07.lease-run-identity/v1', init=False)

    def __post_init__(self):
        if (not _name(self.lineage_id) or not _sha(self.initial_generation_digest)
                or not _sha(self.topology_digest) or not isinstance(self.origin_checkpoint, Checkpoint)):
            _invalid('BAMF_ATLAS_LEASE_RUN_IDENTITY_INVALID')


@dataclass(frozen=True)
class DeltaBudgetPolicy:
    version: str = 'bilqis.c07.initial-delta/v1'
    max_capabilities: int = 9
    max_new_semantic_identities: int = 16

    def __post_init__(self):
        if (not _name(self.version) or type(self.max_capabilities) is not int
                or not 1 <= self.max_capabilities <= 9
                or type(self.max_new_semantic_identities) is not int
                or self.max_new_semantic_identities < 1
                or (self.version == 'bilqis.c07.initial-delta/v1'
                    and self.max_new_semantic_identities != 16)):
            _invalid('BAMF_ATLAS_DELTA_BUDGET_POLICY_INVALID')


@dataclass(frozen=True)
class AtlasSourceApproval:
    approval_id: str
    atlas_release_sha256: str
    source_family_ids: tuple[str, ...]
    operator_ids: tuple[str, ...]
    rights_receipt_sha256: str
    rights_epoch: int
    prerequisite_policy_sha256: str
    progression_policy_sha256: str
    authority_audit_receipt_sha256: str
    audit_passed: bool
    rights_compatible: bool
    source_owner: str
    signature_hex: str
    delta_budget_policy: DeltaBudgetPolicy = field(default_factory=DeltaBudgetPolicy)
    verification_mode: str = field(default='DISPOSABLE_CONTRACT', init=False)
    schema_version: str = field(default='bilqis.c07.atlas-source-approval/v1', init=False)

    def __post_init__(self):
        if (not _name(self.approval_id) or not _name(self.source_owner)
                or not _names(self.source_family_ids) or not _names(self.operator_ids, allow_empty=True)
                or not isinstance(self.delta_budget_policy, DeltaBudgetPolicy)
                or not all(_sha(value) for value in (self.atlas_release_sha256, self.rights_receipt_sha256,
                    self.prerequisite_policy_sha256, self.progression_policy_sha256,
                    self.authority_audit_receipt_sha256))
                or type(self.rights_epoch) is not int or self.rights_epoch < 0
                or type(self.audit_passed) is not bool or type(self.rights_compatible) is not bool
                or not isinstance(self.signature_hex, str)
                or re.fullmatch('[0-9a-f]{128}', self.signature_hex) is None):
            _invalid('BAMF_ATLAS_SOURCE_APPROVAL_INVALID')

    def signing_bytes(self):
        payload = asdict(self)
        del payload['signature_hex']
        return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                          allow_nan=False).encode('utf-8')

    def verify_signature(self, registry):
        if not isinstance(registry, SourceAuthorityRegistry):
            _invalid('BAMF_ATLAS_SOURCE_REGISTRY_REQUIRED')
        registry.verify_detached(self.source_owner,
            DependencyRef(DependencyKind.ARTIFACT, 'atlas-approval:' + self.approval_id),
            self.signature_hex, self.signing_bytes())

    def verify(self, registry):
        self.verify_signature(registry)
        if not self.audit_passed or not self.rights_compatible:
            _invalid('BAMF_ATLAS_SOURCE_OR_RIGHTS_HELD')


@dataclass(frozen=True)
class ResourceCeiling:
    max_semantic_banks: int
    max_motif_pages: int
    max_total_semantic_identities: int
    max_memory_bytes: int
    max_disk_bytes: int

    def __post_init__(self):
        if any(type(value) is not int or value < 1 for value in asdict(self).values()):
            _invalid('BAMF_ATLAS_RESOURCE_CEILING_INVALID')


@dataclass(frozen=True)
class AtlasAdmissionLease:
    lease_id: str
    run_identity: LeaseRunIdentity
    source_approval: AtlasSourceApproval
    resource_ceiling: ResourceCeiling
    requested_at: int
    human_command_sha256: str
    admission_policy: str = field(default='atlas-release', init=False)
    schema_version: str = field(default='bilqis.c07.atlas-admission-lease/v1', init=False)

    def __post_init__(self):
        if (not _name(self.lease_id) or not isinstance(self.run_identity, LeaseRunIdentity)
                or not isinstance(self.source_approval, AtlasSourceApproval)
                or not isinstance(self.resource_ceiling, ResourceCeiling)
                or type(self.requested_at) is not int or self.requested_at < 0
                or not _sha(self.human_command_sha256)):
            _invalid('BAMF_ATLAS_ADMISSION_LEASE_INVALID')

    def digest(self):
        return contract_digest(self)


def issue_atlas_lease(lease_id, run_identity, source_approval, resource_ceiling, *,
                      requested_at, human_command_sha256, human_started, registry):
    if human_started is not True or not isinstance(source_approval, AtlasSourceApproval):
        _invalid('BAMF_ATLAS_EXPLICIT_HUMAN_REQUEST_REQUIRED')
    source_approval.verify(registry)
    return AtlasAdmissionLease(lease_id, run_identity, source_approval, resource_ceiling,
                               requested_at, human_command_sha256)


def _store(root, *, fixture_authority=True):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        _invalid('BAMF_ATLAS_LEASE_UNSAFE_ROOT')
    # This provisional fixture authority must never attach to actual run custody.
    if fixture_authority and any((root / name).exists() or (root / name).is_symlink()
                                 for name in ('state.json', 'bundles', 'generations')):
        _invalid('BAMF_ATLAS_FIXTURE_AUTHORITY_FORBIDDEN_FOR_SAVED_RUN')
    for relative in ('autonomy', 'autonomy/atlas-admission', 'autonomy/atlas-admission/leases'):
        path = root / relative
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            _invalid('BAMF_ATLAS_LEASE_UNSAFE_PATH')
    return root / 'autonomy/atlas-admission'


def _lease_from_json(payload):
    try:
        run = payload['run_identity']
        approval = payload['source_approval']
        record = AtlasAdmissionLease(payload['lease_id'],
            LeaseRunIdentity(run['lineage_id'], run['initial_generation_digest'], run['topology_digest'],
                             Checkpoint(**run['origin_checkpoint'])),
            AtlasSourceApproval(approval['approval_id'], approval['atlas_release_sha256'],
                tuple(approval['source_family_ids']), tuple(approval['operator_ids']),
                approval['rights_receipt_sha256'], approval['rights_epoch'],
                approval['prerequisite_policy_sha256'], approval['progression_policy_sha256'],
                approval['authority_audit_receipt_sha256'], approval['audit_passed'],
                approval['rights_compatible'], approval['source_owner'], approval['signature_hex'],
                delta_budget_policy=DeltaBudgetPolicy(**approval['delta_budget_policy'])),
            ResourceCeiling(**payload['resource_ceiling']), payload['requested_at'], payload['human_command_sha256'])
        if json.loads(json.dumps(asdict(record))) != payload:
            _invalid('BAMF_ATLAS_LEASE_SCHEMA_DRIFT')
        return record
    except (KeyError, TypeError, ValueError):
        _invalid('BAMF_ATLAS_LEASE_PAYLOAD_INVALID')


def read_atlas_lease(run_dir, independently_loaded_run, *, registry):
    directory = _store(run_dir)
    reference = directory / 'current.json'
    if reference.is_symlink():
        _invalid('BAMF_ATLAS_LEASE_UNSAFE_PATH')
    if not reference.exists():
        return None
    try:
        payload = json.loads(reference.read_text(encoding='utf-8'))
        if (set(payload) != {'schema', 'run_identity_digest', 'lease_sha256', 'lease_file'}
                or payload['schema'] != 'bilqis.c07.atlas-lease-reference/v1'
                or not _sha(payload['lease_sha256'])
                or payload['run_identity_digest'] != contract_digest(independently_loaded_run)):
            _invalid('BAMF_ATLAS_LEASE_REFERENCE_DRIFT')
        relative = 'autonomy/atlas-admission/leases/' + payload['lease_sha256'] + '.json'
        if payload['lease_file'] != relative:
            _invalid('BAMF_ATLAS_LEASE_UNSAFE_PATH')
        path = Path(run_dir) / relative
        if path.is_symlink() or not path.is_file():
            _invalid('BAMF_ATLAS_LEASE_REFERENCED_FILE_MISSING')
        lease = _lease_from_json(json.loads(path.read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError):
        _invalid('BAMF_ATLAS_LEASE_READ_FAILED')
    if lease.digest() != payload['lease_sha256'] or lease.run_identity != independently_loaded_run:
        _invalid('BAMF_ATLAS_LEASE_RUN_OR_CONTENT_DRIFT')
    lease.source_approval.verify(registry)
    return lease


def persist_atlas_lease(run_dir, lease, *, independently_loaded_run, registry):
    if (not isinstance(lease, AtlasAdmissionLease)
            or not isinstance(independently_loaded_run, LeaseRunIdentity)
            or lease.run_identity != independently_loaded_run):
        _invalid('BAMF_ATLAS_LEASE_RUN_IDENTITY_DRIFT')
    lease.source_approval.verify(registry)
    directory = _store(run_dir)
    reference = directory / 'current.json'
    prior = read_atlas_lease(run_dir, independently_loaded_run, registry=registry)
    if prior is not None:
        if prior != lease:
            _invalid('BAMF_ATLAS_LEASE_EXPLICIT_RENEWAL_REQUIRED')
        return reference
    relative = 'autonomy/atlas-admission/leases/' + lease.digest() + '.json'
    path = Path(run_dir) / relative
    if path.is_symlink():
        _invalid('BAMF_ATLAS_LEASE_UNSAFE_PATH')
    if path.exists():
        try:
            if _lease_from_json(json.loads(path.read_text(encoding='utf-8'))) != lease:
                _invalid('BAMF_ATLAS_LEASE_IMMUTABLE_DRIFT')
        except (OSError, ValueError):
            _invalid('BAMF_ATLAS_LEASE_READ_FAILED')
    else:
        _durable_json(path, asdict(lease))
    _durable_json(reference, {'schema': 'bilqis.c07.atlas-lease-reference/v1',
        'run_identity_digest': contract_digest(independently_loaded_run),
        'lease_sha256': lease.digest(), 'lease_file': relative})
    if read_atlas_lease(run_dir, independently_loaded_run, registry=registry) != lease:
        _invalid('BAMF_ATLAS_LEASE_READBACK_DRIFT')
    return reference


def advance_atlas_frontier(current, proposal, lease):
    from .atlas_admission_policy import advance_atlas_frontier as advance
    return advance(current, proposal, lease)


def add_atlas_admission_arguments(parser):
    parser.add_argument('--admission-policy', choices=('staged', 'atlas-release'), default='staged',
                        help='Stage new source successors unless an explicit Atlas admission lease authorizes them.')
    parser.add_argument('--atlas-admission-scope', type=Path,
                        help='Exact versioned Atlas lease request; accepted run/source authority is required.')


def validate_atlas_command_request(args):
    if args.admission_policy == 'staged':
        if args.atlas_admission_scope is not None:
            _invalid('BAMF_ATLAS_SCOPE_REQUIRES_EXPLICIT_POLICY')
        return
    if args.human_run is not True:
        _invalid('BAMF_ATLAS_EXPLICIT_HUMAN_REQUEST_REQUIRED')
    if args.atlas_admission_scope is None:
        _invalid('BAMF_ATLAS_EXPLICIT_SCOPE_FILE_REQUIRED')
    path = Path(args.atlas_admission_scope)
    if path.is_symlink() or not path.is_file():
        _invalid('BAMF_ATLAS_SCOPE_FILE_INVALID')
    try:
        _lease_from_json(json.loads(path.read_text(encoding='utf-8')))
    except (OSError, ValueError):
        _invalid('BAMF_ATLAS_SCOPE_FILE_INVALID')
    # B13's accepted BAMF run owner and the actual A12 authority audit have not
    # arrived through unified. Disposable projections cannot authorize this CLI.
    _invalid('BAMF_ATLAS_ACCEPTED_RUN_AUTHORITY_UNAVAILABLE')


def stage_unleased_atlas_proposal(run_dir, proposal):
    from dataclasses import asdict
    from ..factory.jit_curriculum import CurriculumDeltaProposal, ProposalDisposition
    from .atlas_admission_policy import AdmissionResult, AdmissionStatus
    if not isinstance(proposal, CurriculumDeltaProposal) or proposal.disposition is not ProposalDisposition.PROPOSAL:
        _invalid('BAMF_ATLAS_STAGED_PROPOSAL_REQUIRED')
    try:
        proposal.verify()
    except (ValueError, TypeError):
        _invalid('BAMF_ATLAS_NATIVE_PROPOSAL_CONTEXT_DRIFT')
    directory = _store(run_dir, fixture_authority=False)
    reference = directory / 'current.json'
    if reference.exists() or reference.is_symlink():
        # An unreadable/unverifiable lease is not equivalent to absence of one.
        _invalid('BAMF_ATLAS_ACCEPTED_RUN_OWNER_REQUIRED_FOR_REFERENCED_LEASE')
    result = AdmissionResult(AdmissionStatus.STAGED, proposal.proposal_sha256, None,
        proposal.current_release_sha256, proposal.selected_successor_sha256,
        'EXPLICIT_ATLAS_LEASE_REQUIRED',
        'Keep the exact successor staged; request an approved Atlas scope after accepted run authority and the #510 executor are available.')
    staged = directory / 'staged'
    if staged.is_symlink() or (staged.exists() and not staged.is_dir()):
        _invalid('BAMF_ATLAS_LEASE_UNSAFE_PATH')
    path = staged / (contract_digest(result) + '.json')
    payload = json.loads(json.dumps(asdict(result)))
    if path.is_symlink():
        _invalid('BAMF_ATLAS_LEASE_UNSAFE_PATH')
    if path.exists():
        try:
            if json.loads(path.read_text(encoding='utf-8')) != payload:
                _invalid('BAMF_ATLAS_STAGED_DECISION_IMMUTABLE_DRIFT')
        except (OSError, ValueError):
            _invalid('BAMF_ATLAS_STAGED_DECISION_READ_FAILED')
    else:
        _durable_json(path, payload)
    if json.loads(path.read_text(encoding='utf-8')) != payload:
        _invalid('BAMF_ATLAS_STAGED_DECISION_READBACK_DRIFT')
    return result
