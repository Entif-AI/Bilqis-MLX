"""Explicit disposable lease renewal preserves old artifacts and stale-request fences."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_admission import persist_atlas_lease, read_atlas_lease
from bilqis_mlx.runtime.atlas_admission import renew_atlas_lease
from bilqis_mlx.runtime.tests.test_atlas_admission import _lease, _run, _REGISTRY, _signed


class AtlasLeaseRenewalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.old = _lease()
        self.new = replace(self.old, lease_id='renewed', requested_at=101,
            human_command_sha256='8' * 64,
            source_approval=_signed(replace(self.old.source_approval, atlas_release_sha256='9' * 64)))
        persist_atlas_lease(self.root, self.old, independently_loaded_run=_run(), registry=_REGISTRY)

    def renew(self, **kwargs):
        values = dict(independently_loaded_run=_run(), registry=_REGISTRY,
            expected_prior_lease_sha256=self.old.digest(), human_started=True)
        values.update(kwargs)
        return renew_atlas_lease(self.root, self.new, **values)

    def test_explicit_renewal_and_replay_retain_both_immutable_leases(self):
        path = self.renew()
        original = path.read_bytes()
        self.assertEqual(read_atlas_lease(self.root, _run(), registry=_REGISTRY), self.new)
        self.assertEqual(self.renew(), path)
        self.assertEqual(path.read_bytes(), original)
        files = tuple((self.root / 'autonomy/atlas-admission/leases').glob('*.json'))
        self.assertEqual(len(files), 2)
        self.assertTrue(any(self.old.digest() in file.name for file in files))
        self.assertFalse((self.root / 'state.json').exists())

    def test_stale_request_no_human_and_old_command_reject(self):
        for changes in ({'expected_prior_lease_sha256': '0' * 64}, {'human_started': False}):
            with self.subTest(changes=changes), self.assertRaises(BilqisError):
                self.renew(**changes)
        with self.assertRaises(BilqisError):
            renew_atlas_lease(self.root, replace(self.new, human_command_sha256=self.old.human_command_sha256),
                independently_loaded_run=_run(), registry=_REGISTRY,
                expected_prior_lease_sha256=self.old.digest(), human_started=True)
        self.assertEqual(read_atlas_lease(self.root, _run(), registry=_REGISTRY), self.old)

    def test_interrupted_pointer_publication_retains_prior_then_replays(self):
        from bilqis_mlx.runtime import atlas_admission as atlas_lease_renewal
        original = atlas_lease_renewal._durable_json
        def interrupt(path, data, **kwargs):
            if path.name == 'current.json':
                raise OSError('disposable interruption before pointer publication')
            return original(path, data, **kwargs)
        with patch.object(atlas_lease_renewal, '_durable_json', side_effect=interrupt):
            with self.assertRaises(OSError):
                self.renew()
        self.assertEqual(read_atlas_lease(self.root, _run(), registry=_REGISTRY), self.old)
        self.renew()
        self.assertEqual(read_atlas_lease(self.root, _run(), registry=_REGISTRY), self.new)

    def test_replay_cannot_claim_a_different_predecessor(self):
        self.renew()
        with self.assertRaises(BilqisError):
            self.renew(expected_prior_lease_sha256='0' * 64)

    def test_invalid_replacement_wrong_lineage_and_saved_custody_leave_pointer(self):
        before = (self.root / 'autonomy/atlas-admission/current.json').read_bytes()
        for lease in (replace(self.new, run_identity=replace(_run(), lineage_id='wrong')),
                      replace(self.new, source_approval=replace(self.new.source_approval, signature_hex='0' * 128))):
            with self.assertRaises(BilqisError):
                renew_atlas_lease(self.root, lease, independently_loaded_run=_run(), registry=_REGISTRY,
                    expected_prior_lease_sha256=self.old.digest(), human_started=True)
        (self.root / 'state.json').write_text('{}')
        with self.assertRaises(BilqisError):
            self.renew()
        self.assertEqual((self.root / 'autonomy/atlas-admission/current.json').read_bytes(), before)

    def test_restricted_prior_key_scope_can_be_replaced_with_current_approval(self):
        from bilqis_mlx.runtime.atlas_revalidation import SourceAuthorityRegistry, SourceAuthorityScope
        from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
        approval = _signed(replace(self.new.source_approval, approval_id='current-approved-atlas'))
        self.new = replace(self.new, source_approval=approval)
        registry = SourceAuthorityRegistry((replace(_REGISTRY.keys[0], allowed_scopes=(
            SourceAuthorityScope(DependencyKind.ARTIFACT, 'atlas-approval:current-approved-atlas'),)),))
        self.renew(registry=registry)
        self.assertEqual(read_atlas_lease(self.root, _run(), registry=registry), self.new)

    def test_competing_renewals_have_exactly_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        other = replace(self.new, lease_id='competing', human_command_sha256='7' * 64)
        def attempt(lease):
            try:
                renew_atlas_lease(self.root, lease, independently_loaded_run=_run(), registry=_REGISTRY,
                    expected_prior_lease_sha256=self.old.digest(), human_started=True)
                return lease
            except BilqisError:
                return None
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = tuple(workers.map(attempt, (self.new, other)))
        winners = tuple(item for item in results if item is not None)
        self.assertEqual(len(winners), 1)
        self.assertEqual(read_atlas_lease(self.root, _run(), registry=_REGISTRY), winners[0])

    def test_request_identity_time_and_narrowed_scope(self):
        for lease in (replace(self.new, lease_id=self.old.lease_id),
                      replace(self.new, requested_at=self.old.requested_at)):
            with self.assertRaises(BilqisError):
                renew_atlas_lease(self.root, lease, independently_loaded_run=_run(), registry=_REGISTRY,
                    expected_prior_lease_sha256=self.old.digest(), human_started=True)
        self.new = replace(self.new, source_approval=_signed(replace(self.new.source_approval, operator_ids=())))
        self.renew()
        self.assertEqual(read_atlas_lease(self.root, _run(), registry=_REGISTRY).source_approval.operator_ids, ())
