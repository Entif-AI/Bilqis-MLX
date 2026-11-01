"""Atlas lease storage behavior through its public admission boundary."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_admission import (
    AtlasAdmissionLease, issue_atlas_lease, persist_atlas_lease, read_atlas_lease,
)
from bilqis_mlx.runtime.tests.admission.test_atlas_admission import (
    _lease, _run, _scope, _signed, _REGISTRY,
)


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
