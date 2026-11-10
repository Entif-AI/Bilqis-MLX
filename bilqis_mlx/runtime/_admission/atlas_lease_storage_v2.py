"""Separate immutable storage for Atlas admission lease v2 authority."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import json
from pathlib import Path

from ..learning.champions import Checkpoint
from ..semantics.domains import contract_digest
from .atlas_lease_contracts import (
    AtlasAdmissionLeaseV2,
    AtlasSourceApproval,
    DeltaBudgetPolicy,
    LeaseRunIdentity,
    ResourceCeilingV2,
    _invalid,
    _sha,
)
from .atlas_lease_storage import _store
from .state import _durable_json


_REFERENCE_SCHEMA = 'bilqis.c07.atlas-lease-reference/v2'
_LEASE_DIR = 'autonomy/atlas-admission/v2/leases'


def _store_v2(root):
    base = _store(root, fixture_authority=False)
    directory = base / 'v2'
    leases = directory / 'leases'
    for path in (directory, leases):
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            _invalid('BAMF_ATLAS_LEASE_V2_UNSAFE_PATH')
    return directory


def _lease_v2_from_json(payload):
    try:
        run = payload['run_identity']
        approval = payload['source_approval']
        record = AtlasAdmissionLeaseV2(
            payload['lease_id'],
            LeaseRunIdentity(
                run['lineage_id'], run['initial_generation_digest'],
                run['topology_digest'], Checkpoint(**run['origin_checkpoint'])),
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
            ResourceCeilingV2(**payload['resource_ceiling']),
            payload['requested_at'], payload['human_command_sha256'])
        if json.loads(json.dumps(asdict(record))) != payload:
            _invalid('BAMF_ATLAS_LEASE_V2_SCHEMA_DRIFT')
        return record
    except (KeyError, TypeError, ValueError):
        _invalid('BAMF_ATLAS_LEASE_V2_PAYLOAD_INVALID')


def _read_atlas_lease_v2(run_dir, independently_loaded_run, *, registry,
                         current_authority=True):
    directory = _store_v2(run_dir)
    reference = directory / 'current.json'
    if reference.is_symlink():
        _invalid('BAMF_ATLAS_LEASE_V2_UNSAFE_PATH')
    if not reference.exists():
        return None
    try:
        payload = json.loads(reference.read_text(encoding='utf-8'))
        if (set(payload) != {'schema', 'run_identity_digest', 'lease_sha256', 'lease_file'}
                or payload['schema'] != _REFERENCE_SCHEMA
                or not _sha(payload['lease_sha256'])
                or payload['run_identity_digest'] != contract_digest(independently_loaded_run)):
            _invalid('BAMF_ATLAS_LEASE_V2_REFERENCE_DRIFT')
        relative = _LEASE_DIR + '/' + payload['lease_sha256'] + '.json'
        if payload['lease_file'] != relative:
            _invalid('BAMF_ATLAS_LEASE_V2_UNSAFE_PATH')
        path = Path(run_dir) / relative
        if path.is_symlink() or not path.is_file():
            _invalid('BAMF_ATLAS_LEASE_V2_REFERENCED_FILE_MISSING')
        lease = _lease_v2_from_json(json.loads(path.read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError):
        _invalid('BAMF_ATLAS_LEASE_V2_READ_FAILED')
    if (lease.digest() != payload['lease_sha256']
            or lease.run_identity != independently_loaded_run):
        _invalid('BAMF_ATLAS_LEASE_V2_RUN_OR_CONTENT_DRIFT')
    if current_authority:
        lease.source_approval.verify(registry)
    return lease


def _persist_atlas_lease_v2_locked(run_dir, lease, *, independently_loaded_run,
                                   registry):
    if (not isinstance(lease, AtlasAdmissionLeaseV2)
            or not isinstance(independently_loaded_run, LeaseRunIdentity)
            or lease.run_identity != independently_loaded_run):
        _invalid('BAMF_ATLAS_LEASE_V2_RUN_IDENTITY_DRIFT')
    lease.source_approval.verify(registry)
    directory = _store_v2(run_dir)
    reference = directory / 'current.json'
    prior = _read_atlas_lease_v2(
        run_dir, independently_loaded_run, registry=registry)
    if prior is not None:
        if prior != lease:
            _invalid('BAMF_ATLAS_LEASE_V2_EXPLICIT_RENEWAL_REQUIRED')
        return reference
    relative = _LEASE_DIR + '/' + lease.digest() + '.json'
    path = Path(run_dir) / relative
    if path.is_symlink():
        _invalid('BAMF_ATLAS_LEASE_V2_UNSAFE_PATH')
    if path.exists():
        try:
            if _lease_v2_from_json(json.loads(path.read_text(encoding='utf-8'))) != lease:
                _invalid('BAMF_ATLAS_LEASE_V2_IMMUTABLE_DRIFT')
        except (OSError, ValueError):
            _invalid('BAMF_ATLAS_LEASE_V2_READ_FAILED')
    else:
        _durable_json(path, asdict(lease))
    _durable_json(reference, {
        'schema': _REFERENCE_SCHEMA,
        'run_identity_digest': contract_digest(independently_loaded_run),
        'lease_sha256': lease.digest(),
        'lease_file': relative,
    })
    if _read_atlas_lease_v2(
            run_dir, independently_loaded_run, registry=registry) != lease:
        _invalid('BAMF_ATLAS_LEASE_V2_READBACK_DRIFT')
    return reference


@contextmanager
def _atlas_lease_v2_lock(run_dir):
    import fcntl
    import os
    import stat

    directory = _store_v2(run_dir)
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / 'writer.lock'
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            _invalid('BAMF_ATLAS_LEASE_V2_UNSAFE_LOCK')
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)
