"""Immutable lease storage, readback and exclusive disposable-writer locking."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import json
from pathlib import Path

from ..learning.champions import Checkpoint
from ..semantics.domains import contract_digest
from .atlas_lease_contracts import (
    AtlasAdmissionLease, AtlasSourceApproval, DeltaBudgetPolicy, LeaseRunIdentity,
    ResourceCeiling, _invalid, _sha,
)
from .state import _durable_json


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


def _read_atlas_lease(run_dir, independently_loaded_run, *, registry, current_authority=True):
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
    if current_authority:
        lease.source_approval.verify(registry)
    return lease


def _persist_atlas_lease_locked(run_dir, lease, *, independently_loaded_run, registry):
    if (not isinstance(lease, AtlasAdmissionLease)
            or not isinstance(independently_loaded_run, LeaseRunIdentity)
            or lease.run_identity != independently_loaded_run):
        _invalid('BAMF_ATLAS_LEASE_RUN_IDENTITY_DRIFT')
    lease.source_approval.verify(registry)
    directory = _store(run_dir)
    reference = directory / 'current.json'
    prior = _read_atlas_lease(run_dir, independently_loaded_run, registry=registry)
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
    if _read_atlas_lease(run_dir, independently_loaded_run, registry=registry) != lease:
        _invalid('BAMF_ATLAS_LEASE_READBACK_DRIFT')
    return reference


@contextmanager
def _atlas_lease_lock(run_dir):
    import fcntl
    import os
    import stat
    directory = _store(run_dir)
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / 'writer.lock'
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            _invalid('BAMF_ATLAS_LEASE_UNSAFE_LOCK')
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)
