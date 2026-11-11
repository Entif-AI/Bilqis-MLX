"""Atlas lease storage behavior through its public admission boundary."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_admission import (
    AtlasAdmissionLease, issue_atlas_lease, persist_atlas_lease, read_atlas_lease,
)
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import (
    _lease, _run, _scope, _signed, _REGISTRY,
)
import bilqis_mlx.runtime.atlas_lease_storage as storage


class AtlasLeaseStorageTests(unittest.TestCase):
    def test_exact_roundtrip_idempotence_and_independent_run_identity(self):
        lease = _lease()
        self.assertIsInstance(lease, AtlasAdmissionLease)
        self.assertEqual(lease.run_identity.verification_mode, 'DISPOSABLE_CONTRACT')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertIsNone(read_atlas_lease(root, _run(), registry=_REGISTRY))
            reference = persist_atlas_lease(root, lease, independently_loaded_run=_run(), registry=_REGISTRY)
            self.assertEqual(read_atlas_lease(root, _run(), registry=_REGISTRY), lease)
            self.assertEqual(persist_atlas_lease(root, lease, independently_loaded_run=_run(), registry=_REGISTRY), reference)
            with self.assertRaises(BilqisError):
                read_atlas_lease(root, replace(_run(), lineage_id='copied-lineage'), registry=_REGISTRY)
            self.assertFalse((root / 'state.json').exists())
            self.assertFalse((root / 'events.jsonl').exists())
            self.assertFalse((root / 'bundles').exists())


    def test_missing_tampered_lease_and_unequal_renewal_do_not_become_no_lease(self):
        lease = _lease()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = persist_atlas_lease(root, lease, independently_loaded_run=_run(), registry=_REGISTRY)
            with self.assertRaises(BilqisError):
                persist_atlas_lease(root, replace(lease, human_command_sha256='9' * 64),
                                    independently_loaded_run=_run(), registry=_REGISTRY)
            payload = json.loads(reference.read_text())
            immutable = root / payload['lease_file']
            original = immutable.read_bytes()
            immutable.unlink()
            with self.assertRaises(BilqisError):
                read_atlas_lease(root, _run(), registry=_REGISTRY)
            immutable.write_bytes(original.replace(b'fixture-lineage', b'another-lineage'))
            with self.assertRaises(BilqisError):
                read_atlas_lease(root, _run(), registry=_REGISTRY)


    def test_fixture_lease_cannot_attach_to_a_real_saved_run_or_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'state.json').write_text('{}')
            with self.assertRaises(BilqisError):
                persist_atlas_lease(root, _lease(), independently_loaded_run=_run(), registry=_REGISTRY)
            (root / 'state.json').unlink()
            outside = root / 'outside'
            outside.mkdir()
            (root / 'autonomy').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(BilqisError):
                persist_atlas_lease(root, _lease(), independently_loaded_run=_run(), registry=_REGISTRY)
            self.assertEqual(tuple(outside.iterdir()), ())

    def test_every_b13_custody_marker_rejects_fixture_authority_before_atlas_state(self):
        markers = (
            'bamf-state.json', 'bamf-bundles', 'bamf-acceptance',
            '.bamf-pointer.lock', '.bamf-staging',
        )
        for marker in markers:
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path = root / marker
                if marker in {'bamf-bundles', 'bamf-acceptance', '.bamf-staging'}:
                    path.mkdir()
                else:
                    path.write_text('')
                with self.assertRaises(BilqisError) as failure:
                    persist_atlas_lease(
                        root, _lease(), independently_loaded_run=_run(), registry=_REGISTRY)
                self.assertEqual(
                    failure.exception.context['reason'],
                    'BAMF_ATLAS_FIXTURE_AUTHORITY_FORBIDDEN_FOR_SAVED_RUN')
                self.assertFalse((root / 'autonomy').exists())

    def test_epoch_classifier_is_read_only_and_orders_v1_then_v2_path_safety(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(storage.classify_accepted_atlas_epoch(root), 'staged')
            self.assertFalse((root / 'autonomy').exists())

            v2 = root / 'autonomy/atlas-admission/v2/current.json'
            v2.parent.mkdir(parents=True)
            v2.write_text('{}')
            self.assertEqual(storage.classify_accepted_atlas_epoch(root), 'v2')

            v1 = root / 'autonomy/atlas-admission/current.json'
            v1.write_text('{}')
            with self.assertRaises(BilqisError) as dual:
                storage.classify_accepted_atlas_epoch(root)
            self.assertEqual(
                dual.exception.context['reason'],
                'BAMF_ATLAS_AUTHORITY_EPOCH_CONFLICT')

            v1.unlink()
            outside = root / 'outside'
            outside.write_text('{}')
            v1.symlink_to(outside)
            v2.unlink()
            v2.mkdir()
            with self.assertRaises(BilqisError) as unsafe:
                storage.classify_accepted_atlas_epoch(root)
            self.assertEqual(
                unsafe.exception.context['reason'],
                'BAMF_ATLAS_LEASE_UNSAFE_PATH')

    def test_epoch_lock_release_failure_preserves_body_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            real = storage.fcntl.flock

            def fail_unlock(fd, operation):
                if operation == storage.fcntl.LOCK_UN:
                    raise OSError('unlock failed')
                return real(fd, operation)

            original = RuntimeError('body failed')
            with patch.object(storage.fcntl, 'flock', side_effect=fail_unlock), \
                    self.assertRaises(RuntimeError) as failure:
                with storage._atlas_authority_epoch_lock(root):
                    raise original
            self.assertIs(failure.exception, original)
            self.assertIn(
                'BAMF_ATLAS_AUTHORITY_EPOCH_LOCK_RELEASE_FAILED:unlock',
                getattr(original, '__notes__', ()))

    def test_epoch_lock_rejects_unsafe_shape_and_acquire_release_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock = root / 'autonomy/atlas-admission/authority-epoch.lock'
            lock.parent.mkdir(parents=True)
            outside = root / 'outside'
            outside.write_text('x')
            lock.symlink_to(outside)
            with self.assertRaises(BilqisError) as unsafe:
                with storage._atlas_authority_epoch_lock(root):
                    self.fail('unsafe lock must not enter')
            self.assertEqual(
                unsafe.exception.context['reason'],
                'BAMF_ATLAS_AUTHORITY_EPOCH_UNSAFE_LOCK')

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(storage.fcntl, 'flock', side_effect=OSError('busy')), \
                    self.assertRaises(BilqisError) as acquire:
                with storage._atlas_authority_epoch_lock(root):
                    self.fail('acquire failure must not enter')
            self.assertEqual(
                acquire.exception.context['reason'],
                'BAMF_ATLAS_AUTHORITY_EPOCH_LOCK_UNAVAILABLE')

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            real = storage.fcntl.flock

            def fail_unlock(fd, operation):
                if operation == storage.fcntl.LOCK_UN:
                    raise OSError('unlock failed')
                return real(fd, operation)

            with patch.object(storage.fcntl, 'flock', side_effect=fail_unlock), \
                    self.assertRaises(BilqisError) as release:
                with storage._atlas_authority_epoch_lock(root):
                    pass
            self.assertEqual(
                release.exception.context['reason'],
                'BAMF_ATLAS_AUTHORITY_EPOCH_LOCK_RELEASE_FAILED')

    def test_read_only_epoch_precheck_does_not_create_epoch_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / 'autonomy/atlas-admission/current.json'
            current.parent.mkdir(parents=True)
            current.write_text('{}')
            with self.assertRaises(BilqisError) as failure:
                storage.require_accepted_atlas_epoch_available_v2(root)
            self.assertEqual(
                failure.exception.context['reason'],
                'BAMF_ATLAS_V2_LEGACY_AUTHORITY_PRESENT')
            self.assertFalse((current.parent / 'authority-epoch.lock').exists())
