"""Operator request, staging, and fixture-facing C07 admission surface."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from bilqis_mlx.runtime.atlas_lease_contracts import AtlasAdmissionLease, AtlasSourceApproval, _invalid
from bilqis_mlx.runtime.atlas_lease_storage import (
    _atlas_lease_lock,
    _lease_from_json,
    _persist_atlas_lease_locked,
    _read_atlas_lease,
    _store,
)
from bilqis_mlx.runtime.state import _durable_json
from bilqis_mlx.semantics.domains import contract_digest


def issue_atlas_lease(lease_id, run_identity, source_approval, resource_ceiling, *,
                      requested_at, human_command_sha256, human_started, registry):
    if human_started is not True or not isinstance(source_approval, AtlasSourceApproval):
        _invalid('BAMF_ATLAS_EXPLICIT_HUMAN_REQUEST_REQUIRED')
    source_approval.verify(registry)
    return AtlasAdmissionLease(lease_id, run_identity, source_approval, resource_ceiling,
                               requested_at, human_command_sha256)


def advance_atlas_frontier(current, proposal, lease):
    from bilqis_mlx.runtime.atlas_admission_policy import advance_atlas_frontier as advance
    return advance(current, proposal, lease)


def advance_atlas_frontier_v2(current, delta, lease):
    from bilqis_mlx.runtime.atlas_admission_policy_v2 import advance_atlas_frontier_v2 as advance
    return advance(current, delta, lease)


def add_atlas_admission_arguments(parser, *, admission_policy_action=None):
    policy_kwargs = {
        'choices': ('staged', 'atlas-release'),
        'default': 'staged',
        'help': 'Stage new source successors unless an explicit Atlas admission lease authorizes them.',
    }
    if admission_policy_action is not None:
        policy_kwargs['action'] = admission_policy_action
    parser.add_argument('--admission-policy', **policy_kwargs)
    parser.add_argument('--atlas-admission-scope', type=Path,
                        help='Exact versioned Atlas lease request; accepted run/source authority is required.')


def read_atlas_lease_request(path):
    """Parse one caller-supplied lease request without granting run authority."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        _invalid('BAMF_ATLAS_SCOPE_FILE_INVALID')
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError):
        _invalid('BAMF_ATLAS_SCOPE_FILE_INVALID')
    return _lease_from_json(payload)


def validate_atlas_lease_request(args):
    """Validate explicit human selection and return request data only."""
    if args.human_run is not True:
        _invalid('BAMF_ATLAS_EXPLICIT_HUMAN_REQUEST_REQUIRED')
    if args.atlas_admission_scope is None:
        _invalid('BAMF_ATLAS_EXPLICIT_SCOPE_FILE_REQUIRED')
    return read_atlas_lease_request(args.atlas_admission_scope)


def validate_atlas_command_request(args):
    if args.admission_policy == 'staged':
        if args.atlas_admission_scope is not None:
            _invalid('BAMF_ATLAS_SCOPE_REQUIRES_EXPLICIT_POLICY')
        return
    validate_atlas_lease_request(args)
    _invalid('BAMF_ATLAS_ACCEPTED_RUN_AUTHORITY_UNAVAILABLE')


def _validated_frontier_proposal(proposal):
    from bilqis_mlx.factory.jit_curriculum import CurriculumDeltaProposal, ProposalDisposition
    if (not isinstance(proposal, CurriculumDeltaProposal)
            or proposal.disposition is not ProposalDisposition.PROPOSAL):
        _invalid('BAMF_ATLAS_STAGED_PROPOSAL_REQUIRED')
    try:
        proposal.verify()
    except (ValueError, TypeError):
        _invalid('BAMF_ATLAS_NATIVE_PROPOSAL_CONTEXT_DRIFT')
    return proposal


def _persist_staged_atlas_result(run_dir, result):
    from bilqis_mlx.runtime.atlas_admission_policy import AdmissionResult, AdmissionStatus
    if not isinstance(result, AdmissionResult) or result.status is not AdmissionStatus.STAGED:
        _invalid('BAMF_ATLAS_STAGED_RESULT_REQUIRED')
    directory = _store(run_dir, fixture_authority=False)
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


def stage_unleased_atlas_proposal(run_dir, proposal):
    from bilqis_mlx.runtime.atlas_admission_policy import AdmissionResult, AdmissionStatus
    proposal = _validated_frontier_proposal(proposal)
    directory = _store(run_dir, fixture_authority=False)
    reference = directory / 'current.json'
    if reference.exists() or reference.is_symlink():
        _invalid('BAMF_ATLAS_ACCEPTED_RUN_OWNER_REQUIRED_FOR_REFERENCED_LEASE')
    return _persist_staged_atlas_result(run_dir, AdmissionResult(
        AdmissionStatus.STAGED, proposal.proposal_sha256, None,
        proposal.current_release_sha256, proposal.selected_successor_sha256,
        'EXPLICIT_ATLAS_LEASE_REQUIRED',
        'Keep the exact successor staged; request an approved Atlas scope after accepted run authority is available.'))


def dispatch_atlas_frontier_proposal(run_dir, proposal):
    """Route one frontier proposal through accepted lease custody or safe staging."""
    from bilqis_mlx.runtime.atlas_admission_policy import AdmissionResult, AdmissionStatus
    proposal = _validated_frontier_proposal(proposal)
    directory = _store(run_dir, fixture_authority=False)
    reference = directory / 'current.json'
    if reference.is_symlink():
        _invalid('BAMF_ATLAS_LEASE_UNSAFE_PATH')
    if not reference.exists():
        return stage_unleased_atlas_proposal(run_dir, proposal)
    from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
    from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_lease
    host = AcceptedRuntimeHost(Path(run_dir))
    lease = read_accepted_atlas_lease(
        run_dir, source_authority=host.source_authority())
    if lease is None:
        _invalid('BAMF_ATLAS_ACCEPTED_RUN_OWNER_REQUIRED_FOR_REFERENCED_LEASE')
    return _persist_staged_atlas_result(run_dir, AdmissionResult(
        AdmissionStatus.STAGED, proposal.proposal_sha256, lease.digest(),
        proposal.current_release_sha256, proposal.selected_successor_sha256,
        'PRODUCTION_DELTA_AUTHORITY_UNAVAILABLE',
        'Keep the exact successor staged until owner-derived delta scope and source-bundle location are available.'))


def read_atlas_lease(run_dir, independently_loaded_run, *, registry):
    return _read_atlas_lease(run_dir, independently_loaded_run, registry=registry)


def persist_atlas_lease(run_dir, lease, *, independently_loaded_run, registry):
    from bilqis_mlx.runtime._coordination import run_root_claim
    with run_root_claim(Path(run_dir), create_parent=False):
        with _atlas_lease_lock(run_dir):
            return _persist_atlas_lease_locked(
                run_dir, lease, independently_loaded_run=independently_loaded_run,
                registry=registry)
