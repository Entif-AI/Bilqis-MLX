"""C07 owner for non-authoritative BAMF v2 enrollment requests."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from bilqis_mlx.errors import BilqisError
from .atlas_lease_contracts import (
    AtlasAdmissionEnrollmentRequestV2,
    AtlasSourceApproval,
    DeltaBudgetPolicy,
    ResourceCeilingV2,
    _invalid,
)


def _request_from_json(payload) -> AtlasAdmissionEnrollmentRequestV2:
    expected = {
        'lease_id', 'requested_run_id', 'requested_run_seed',
        'requested_topology_digest', 'source_approval', 'resource_ceiling',
        'requested_at', 'human_command_sha256', 'admission_policy',
        'schema_version',
    }
    try:
        if not isinstance(payload, dict) or set(payload) != expected:
            raise ValueError
        if (payload['admission_policy'] != 'atlas-release'
                or payload['schema_version']
                != 'bilqis.c07.atlas-admission-enrollment-request/v2'):
            raise ValueError
        approval = payload['source_approval']
        ceiling = payload['resource_ceiling']
        if not isinstance(approval, dict) or not isinstance(ceiling, dict):
            raise ValueError
        request = AtlasAdmissionEnrollmentRequestV2(
            payload['lease_id'], payload['requested_run_id'],
            payload['requested_run_seed'], payload['requested_topology_digest'],
            AtlasSourceApproval(
                approval['approval_id'], approval['atlas_release_sha256'],
                tuple(approval['source_family_ids']), tuple(approval['operator_ids']),
                approval['rights_receipt_sha256'], approval['rights_epoch'],
                approval['prerequisite_policy_sha256'],
                approval['progression_policy_sha256'],
                approval['authority_audit_receipt_sha256'], approval['audit_passed'],
                approval['rights_compatible'], approval['source_owner'],
                approval['signature_hex'],
                delta_budget_policy=DeltaBudgetPolicy(**approval['delta_budget_policy'])),
            ResourceCeilingV2(**ceiling), payload['requested_at'],
            payload['human_command_sha256'])
        if json.loads(json.dumps(asdict(request))) != payload:
            raise ValueError
        return request
    except (KeyError, TypeError, ValueError, BilqisError):
        # Caller request parsing has one intentionally narrow public failure surface.
        _invalid('BAMF_ATLAS_ENROLLMENT_REQUEST_INVALID')


def read_atlas_enrollment_request_v2(path) -> AtlasAdmissionEnrollmentRequestV2:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        _invalid('BAMF_ATLAS_ENROLLMENT_REQUEST_INVALID')
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        _invalid('BAMF_ATLAS_ENROLLMENT_REQUEST_INVALID')
    return _request_from_json(payload)


def _reject_legacy_v1_authority(run_dir: Path) -> None:
    current = run_dir / 'autonomy/atlas-admission/current.json'
    if current.is_symlink():
        _invalid('BAMF_ATLAS_LEASE_UNSAFE_PATH')
    if current.exists():
        if not current.is_file():
            _invalid('BAMF_ATLAS_LEASE_UNSAFE_PATH')
        _invalid('BAMF_ATLAS_V2_LEGACY_AUTHORITY_PRESENT')


def enroll_accepted_atlas_lease_v2(
        run_dir, request: AtlasAdmissionEnrollmentRequestV2, *,
        human_started: bool, source_authority):
    """Derive and persist one v2 lease from accepted BAMF custody."""
    if human_started is not True or type(request) is not AtlasAdmissionEnrollmentRequestV2:
        _invalid('BAMF_ATLAS_V2_EXPLICIT_HUMAN_REQUEST_REQUIRED')
    run_dir = Path(run_dir)
    _reject_legacy_v1_authority(run_dir)

    from bilqis_mlx.runtime.bamf_bundle import (
        load_bamf_generation_authority, read_accepted_generation_feature_receipt,
    )
    pointer = run_dir / 'bamf-state.json'
    student, _manifest_sha256 = load_bamf_generation_authority(pointer)
    identity = student.run_identity
    if identity is None:
        _invalid('BAMF_ATLAS_ACCEPTED_RUN_IDENTITY_REQUIRED')
    features = read_accepted_generation_feature_receipt(pointer)
    if features.source_release_sha256 != identity.initial_release_digest:
        _invalid('BAMF_ATLAS_V2_ACCEPTED_ATLAS_CUSTODY_DRIFT')
    if (request.requested_run_id != identity.run_id
            or request.requested_run_seed != identity.run_seed
            or request.requested_topology_digest != identity.initial_topology_digest):
        _invalid('BAMF_ATLAS_V2_ENROLLMENT_RUN_IDENTITY_DRIFT')
    if request.source_approval.atlas_release_sha256 != features.source_release_sha256:
        _invalid('BAMF_ATLAS_V2_ENROLLMENT_ATLAS_RELEASE_DRIFT')

    from .atlas_admission import _accepted_run_lease_identity, _accepted_source_registry
    from .atlas_lease_v2 import issue_atlas_lease_v2, persist_accepted_atlas_lease_v2
    expected = _accepted_run_lease_identity(run_dir)
    registry = _accepted_source_registry(run_dir, source_authority)
    lease = issue_atlas_lease_v2(
        request.lease_id, expected, request.source_approval,
        request.resource_ceiling, requested_at=request.requested_at,
        human_command_sha256=request.human_command_sha256,
        human_started=human_started, registry=registry)
    persist_accepted_atlas_lease_v2(
        run_dir, lease, source_authority=source_authority)
    from .atlas_lease_v2 import read_accepted_atlas_lease_v2
    persisted = read_accepted_atlas_lease_v2(
        run_dir, source_authority=source_authority)
    if persisted != lease:
        _invalid('BAMF_ATLAS_LEASE_V2_READBACK_DRIFT')
    return persisted


__all__ = (
    'AtlasAdmissionEnrollmentRequestV2', 'read_atlas_enrollment_request_v2',
    'enroll_accepted_atlas_lease_v2',
)
