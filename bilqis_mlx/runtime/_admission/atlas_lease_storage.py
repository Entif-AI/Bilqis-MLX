"""Immutable lease storage, readback and exclusive disposable-writer locking."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import fcntl
import json
import os
from pathlib import Path
import stat

from bilqis_mlx.errors import BilqisError
from ..learning.champions import Checkpoint
from ..semantics.domains import contract_digest
from .atlas_lease_contracts import (
    AtlasAdmissionLease, AtlasSourceApproval, DeltaBudgetPolicy, LeaseRunIdentity,
    ResourceCeiling, _invalid, _sha,
)
from .state import _durable_json


_FIXTURE_RUN_CUSTODY_MARKERS = (
    'state.json', 'bundles', 'generations',
    'bamf-state.json', 'bamf-bundles', 'bamf-acceptance',
    '.bamf-pointer.lock', '.bamf-staging',
)


def _reject_fixture_run_custody(root: Path) -> None:
    root = Path(root)
    for name in _FIXTURE_RUN_CUSTODY_MARKERS:
        path = root / name
        if path.exists() or path.is_symlink():
            _invalid('BAMF_ATLAS_FIXTURE_AUTHORITY_FORBIDDEN_FOR_SAVED_RUN')


def _store(root, *, fixture_authority=True):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        _invalid('BAMF_ATLAS_LEASE_UNSAFE_ROOT')
    # This provisional fixture authority must never attach to actual run custody.
    if fixture_authority:
        _reject_fixture_run_custody(root)
    for relative in ('autonomy', 'autonomy/atlas-admission', 'autonomy/atlas-admission/leases'):
        path = root / relative
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            _invalid('BAMF_ATLAS_LEASE_UNSAFE_PATH')
    return root / 'autonomy/atlas-admission'


def classify_accepted_atlas_epoch(run_dir: Path) -> str:
    """Return staged/v1/v2 without creating accepted authority state."""
    root = Path(run_dir)
    v1 = root / 'autonomy/atlas-admission/current.json'
    v2 = root / 'autonomy/atlas-admission/v2/current.json'
    if v1.is_symlink() or (v1.exists() and not v1.is_file()):
        _invalid('BAMF_ATLAS_LEASE_UNSAFE_PATH')
    if v2.is_symlink() or (v2.exists() and not v2.is_file()):
        _invalid('BAMF_ATLAS_LEASE_V2_UNSAFE_PATH')
    v1_present, v2_present = v1.exists(), v2.exists()
    if v1_present and v2_present:
        _invalid('BAMF_ATLAS_AUTHORITY_EPOCH_CONFLICT')
    if v1_present:
        return 'v1'
    if v2_present:
        return 'v2'
    return 'staged'


def require_accepted_atlas_epoch_available_v2(run_dir: Path) -> None:
    if classify_accepted_atlas_epoch(Path(run_dir)) == 'v1':
        _invalid('BAMF_ATLAS_V2_LEGACY_AUTHORITY_PRESENT')


@contextmanager
def _atlas_authority_epoch_lock(run_dir: Path):
    """Serialize accepted v1/v2 current-reference mutation across epochs."""
    descriptor = None
    locked = False
    try:
        try:
            directory = _store(run_dir, fixture_authority=False)
            directory.mkdir(parents=True, exist_ok=True)
            lock = directory / 'authority-epoch.lock'
            if lock.is_symlink():
                _invalid('BAMF_ATLAS_AUTHORITY_EPOCH_UNSAFE_LOCK')
            flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
            descriptor = os.open(lock, flags, 0o600)
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                _invalid('BAMF_ATLAS_AUTHORITY_EPOCH_UNSAFE_LOCK')
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            locked = True
        except BilqisError:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            raise
        except (OSError, ValueError):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            _invalid('BAMF_ATLAS_AUTHORITY_EPOCH_LOCK_UNAVAILABLE')

        body_error = None
        try:
            yield None
        except BaseException as error:
            body_error = error
            raise
        finally:
            release_failure = None
            if locked:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    release_failure = 'unlock'
            try:
                os.close(descriptor)
            except OSError:
                if release_failure is None:
                    release_failure = 'close'
            if release_failure is not None:
                if body_error is not None:
                    body_error.add_note(
                        'BAMF_ATLAS_AUTHORITY_EPOCH_LOCK_RELEASE_FAILED:'
                        + release_failure)
                else:
                    _invalid('BAMF_ATLAS_AUTHORITY_EPOCH_LOCK_RELEASE_FAILED')
    finally:
        descriptor = None


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


def _read_atlas_lease(
        run_dir, independently_loaded_run, *, registry, current_authority=True,
        fixture_authority=True):
    directory = _store(run_dir, fixture_authority=fixture_authority)
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


def _persist_atlas_lease_locked(
        run_dir, lease, *, independently_loaded_run, registry,
        fixture_authority=True):
    if (not isinstance(lease, AtlasAdmissionLease)
            or not isinstance(independently_loaded_run, LeaseRunIdentity)
            or lease.run_identity != independently_loaded_run):
        _invalid('BAMF_ATLAS_LEASE_RUN_IDENTITY_DRIFT')
    lease.source_approval.verify(registry)
    directory = _store(run_dir, fixture_authority=fixture_authority)
    reference = directory / 'current.json'
    prior = _read_atlas_lease(
        run_dir, independently_loaded_run, registry=registry,
        fixture_authority=fixture_authority)
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
    if _read_atlas_lease(
            run_dir, independently_loaded_run, registry=registry,
            fixture_authority=fixture_authority) != lease:
        _invalid('BAMF_ATLAS_LEASE_READBACK_DRIFT')
    return reference


@contextmanager
def _atlas_lease_lock(run_dir, *, fixture_authority=True):
    import fcntl
    import os
    import stat
    directory = _store(run_dir, fixture_authority=fixture_authority)
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
