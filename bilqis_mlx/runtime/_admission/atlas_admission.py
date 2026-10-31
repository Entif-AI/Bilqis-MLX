"""Structural extraction from atlas_admission.py; behavior preserved."""
from __future__ import annotations
from dataclasses import asdict
import json
from pathlib import Path
from ..semantics.domains import contract_digest
from .state import _durable_json
from .atlas_lease_contracts import AtlasAdmissionLease, AtlasSourceApproval, _invalid, _sha
from .atlas_lease_storage import _atlas_lease_lock, _lease_from_json, _persist_atlas_lease_locked, _read_atlas_lease, _store
from .atlas_lease_contracts import (AtlasAdmissionLease, AtlasSourceApproval, DeltaBudgetPolicy, LeaseRunIdentity, ResourceCeiling, _invalid, _name, _names, _sha)
from .atlas_lease_storage import (_atlas_lease_lock, _lease_from_json, _persist_atlas_lease_locked, _read_atlas_lease, _store)

def issue_atlas_lease(lease_id, run_identity, source_approval, resource_ceiling, *,
                      requested_at, human_command_sha256, human_started, registry):
    if human_started is not True or not isinstance(source_approval, AtlasSourceApproval):
        _invalid('BAMF_ATLAS_EXPLICIT_HUMAN_REQUEST_REQUIRED')
    source_approval.verify(registry)
    return AtlasAdmissionLease(lease_id, run_identity, source_approval, resource_ceiling,
                               requested_at, human_command_sha256)

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

def read_atlas_lease(run_dir, independently_loaded_run, *, registry):
    return _read_atlas_lease(run_dir, independently_loaded_run, registry=registry)

def persist_atlas_lease(run_dir, lease, *, independently_loaded_run, registry):
    with _atlas_lease_lock(run_dir):
        return _persist_atlas_lease_locked(run_dir, lease,
            independently_loaded_run=independently_loaded_run, registry=registry)

def renew_atlas_lease(run_dir, lease, *, independently_loaded_run, registry,
                      expected_prior_lease_sha256, human_started):
    """Renew disposable scope explicitly; caller assertions do not prove human identity."""
    if (human_started is not True or not _sha(expected_prior_lease_sha256)
            or not isinstance(lease, AtlasAdmissionLease)
            or lease.run_identity != independently_loaded_run):
        _invalid('BAMF_ATLAS_LEASE_RENEWAL_ARGUMENT_INVALID')
    lease.source_approval.verify(registry)
    with _atlas_lease_lock(run_dir):
        directory = _store(run_dir)
        prior = _read_atlas_lease(run_dir, independently_loaded_run,
                                 registry=registry, current_authority=False)
        edge = {'schema': 'bilqis.c07.lease-renewal/v1',
                'prior_lease_sha256': expected_prior_lease_sha256,
                'replacement_lease_sha256': lease.digest(),
                'human_command_sha256': lease.human_command_sha256}
        edges = directory / 'renewals'
        if edges.is_symlink() or (edges.exists() and not edges.is_dir()):
            _invalid('BAMF_ATLAS_LEASE_UNSAFE_PATH')
        edge_path = edges / (lease.digest() + '.json')
        if edge_path.is_symlink():
            _invalid('BAMF_ATLAS_LEASE_UNSAFE_PATH')
        if prior == lease:
            if not edge_path.is_file() or json.loads(edge_path.read_text()) != edge:
                _invalid('BAMF_ATLAS_LEASE_RENEWAL_PREDECESSOR_DRIFT')
            return directory / 'current.json'
        if (prior is None or prior.digest() != expected_prior_lease_sha256
                or prior.lease_id == lease.lease_id
                or prior.human_command_sha256 == lease.human_command_sha256
                or lease.requested_at <= prior.requested_at):
            _invalid('BAMF_ATLAS_LEASE_RENEWAL_PREDECESSOR_DRIFT')
        relative = 'autonomy/atlas-admission/leases/' + lease.digest() + '.json'
        path = Path(run_dir) / relative
        for artifact, payload in ((path, asdict(lease)), (edge_path, edge)):
            if artifact.is_symlink():
                _invalid('BAMF_ATLAS_LEASE_UNSAFE_PATH')
            if artifact.exists():
                if json.loads(artifact.read_text()) != json.loads(json.dumps(payload)):
                    _invalid('BAMF_ATLAS_LEASE_IMMUTABLE_DRIFT')
            else:
                _durable_json(artifact, payload)
        reference = directory / 'current.json'
        _durable_json(reference, {'schema': 'bilqis.c07.atlas-lease-reference/v1',
            'run_identity_digest': contract_digest(independently_loaded_run),
            'lease_sha256': lease.digest(), 'lease_file': relative}, replace_existing=True)
        if read_atlas_lease(run_dir, independently_loaded_run, registry=registry) != lease:
            _invalid('BAMF_ATLAS_LEASE_READBACK_DRIFT')
        return reference
