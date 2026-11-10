"""Human-authorized Atlas admission lease v2 issuance and custody."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from ..semantics.domains import contract_digest
from .atlas_lease_contracts import (
    AtlasAdmissionLeaseV2,
    AtlasSourceApproval,
    LeaseRunIdentity,
    ResourceCeilingV2,
    _invalid,
    _sha,
)
from .atlas_lease_storage_v2 import (
    _atlas_lease_v2_lock,
    _persist_atlas_lease_v2_locked,
    _read_atlas_lease_v2,
    _store_v2,
)
from .state import _durable_json


def issue_atlas_lease_v2(
        lease_id, run_identity, source_approval, resource_ceiling, *,
        requested_at, human_command_sha256, human_started, registry):
    if (human_started is not True
            or not isinstance(source_approval, AtlasSourceApproval)
            or not isinstance(resource_ceiling, ResourceCeilingV2)):
        _invalid('BAMF_ATLAS_V2_EXPLICIT_HUMAN_REQUEST_REQUIRED')
    source_approval.verify(registry)
    return AtlasAdmissionLeaseV2(
        lease_id, run_identity, source_approval, resource_ceiling,
        requested_at, human_command_sha256)


def read_atlas_lease_v2(run_dir, independently_loaded_run, *, registry):
    return _read_atlas_lease_v2(
        run_dir, independently_loaded_run, registry=registry)


def persist_atlas_lease_v2(
        run_dir, lease, *, independently_loaded_run, registry):
    with _atlas_lease_v2_lock(run_dir):
        return _persist_atlas_lease_v2_locked(
            run_dir, lease, independently_loaded_run=independently_loaded_run,
            registry=registry)


def persist_accepted_atlas_lease_v2(run_dir, lease, *, source_authority):
    from .atlas_admission import _accepted_run_lease_identity, _accepted_source_registry

    expected = _accepted_run_lease_identity(run_dir)
    if (not isinstance(lease, AtlasAdmissionLeaseV2)
            or lease.run_identity != expected):
        _invalid('BAMF_ATLAS_LEASE_V2_RUN_IDENTITY_DRIFT')
    registry = _accepted_source_registry(run_dir, source_authority)
    with _atlas_lease_v2_lock(run_dir):
        return _persist_atlas_lease_v2_locked(
            run_dir, lease, independently_loaded_run=expected, registry=registry)


def read_accepted_atlas_lease_v2(run_dir, *, source_authority):
    from .atlas_admission import _accepted_run_lease_identity, _accepted_source_registry

    expected = _accepted_run_lease_identity(run_dir)
    registry = _accepted_source_registry(run_dir, source_authority)
    return _read_atlas_lease_v2(
        run_dir, expected, registry=registry)


def renew_atlas_lease_v2(
        run_dir, lease, *, independently_loaded_run, registry,
        expected_prior_lease_sha256, human_started):
    """Explicitly replace one v2 lease without touching v1 current authority."""
    if (human_started is not True or not _sha(expected_prior_lease_sha256)
            or not isinstance(lease, AtlasAdmissionLeaseV2)
            or lease.run_identity != independently_loaded_run):
        _invalid('BAMF_ATLAS_LEASE_V2_RENEWAL_ARGUMENT_INVALID')
    lease.source_approval.verify(registry)
    with _atlas_lease_v2_lock(run_dir):
        directory = _store_v2(run_dir)
        prior = _read_atlas_lease_v2(
            run_dir, independently_loaded_run, registry=registry,
            current_authority=False)
        edge = {
            'schema': 'bilqis.c07.lease-renewal/v2',
            'prior_lease_sha256': expected_prior_lease_sha256,
            'replacement_lease_sha256': lease.digest(),
            'human_command_sha256': lease.human_command_sha256,
        }
        edges = directory / 'renewals'
        if edges.is_symlink() or (edges.exists() and not edges.is_dir()):
            _invalid('BAMF_ATLAS_LEASE_V2_UNSAFE_PATH')
        edge_path = edges / (lease.digest() + '.json')
        if edge_path.is_symlink():
            _invalid('BAMF_ATLAS_LEASE_V2_UNSAFE_PATH')
        if prior == lease:
            if not edge_path.is_file() or json.loads(edge_path.read_text()) != edge:
                _invalid('BAMF_ATLAS_LEASE_V2_RENEWAL_PREDECESSOR_DRIFT')
            return directory / 'current.json'
        if (prior is None or prior.digest() != expected_prior_lease_sha256
                or prior.lease_id == lease.lease_id
                or prior.human_command_sha256 == lease.human_command_sha256
                or lease.requested_at <= prior.requested_at):
            _invalid('BAMF_ATLAS_LEASE_V2_RENEWAL_PREDECESSOR_DRIFT')
        relative = (
            'autonomy/atlas-admission/v2/leases/' + lease.digest() + '.json')
        path = Path(run_dir) / relative
        for artifact, payload in ((path, asdict(lease)), (edge_path, edge)):
            if artifact.is_symlink():
                _invalid('BAMF_ATLAS_LEASE_V2_UNSAFE_PATH')
            if artifact.exists():
                if json.loads(artifact.read_text()) != json.loads(json.dumps(payload)):
                    _invalid('BAMF_ATLAS_LEASE_V2_IMMUTABLE_DRIFT')
            else:
                _durable_json(artifact, payload)
        reference = directory / 'current.json'
        _durable_json(reference, {
            'schema': 'bilqis.c07.atlas-lease-reference/v2',
            'run_identity_digest': contract_digest(independently_loaded_run),
            'lease_sha256': lease.digest(),
            'lease_file': relative,
        }, replace_existing=True)
        if _read_atlas_lease_v2(
                run_dir, independently_loaded_run, registry=registry) != lease:
            _invalid('BAMF_ATLAS_LEASE_V2_READBACK_DRIFT')
        return reference
