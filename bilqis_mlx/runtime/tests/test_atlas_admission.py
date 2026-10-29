"""Provisional lease contracts use isolated state and explicitly disposable authority."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.atlas_admission import (
    AtlasAdmissionLease, AtlasSourceApproval, LeaseRunIdentity, ResourceCeiling,
    issue_atlas_lease, persist_atlas_lease, read_atlas_lease,
)
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.runtime.atlas_revalidation import SourceAuthorityRegistry, SourceAuthorityScope
from bilqis_mlx.learning.tests.test_atlas_salience import _REGISTRY, _signed
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind

_REGISTRY = SourceAuthorityRegistry((replace(_REGISTRY.keys[0], allowed_scopes=tuple(sorted(
    (*_REGISTRY.keys[0].allowed_scopes, SourceAuthorityScope(DependencyKind.ARTIFACT, 'atlas-approval:')),
    key=lambda scope: (scope.kind.value, scope.key_prefix)))),))


def _run():
    return LeaseRunIdentity('fixture-lineage', '1' * 64, ModelTopologySpecV2().digest,
                            Checkpoint('2' * 64, 'bundles/disposable-origin', 0, True))


def _scope():
    return _signed(AtlasSourceApproval('fixture-approved-atlas', 'a' * 64,
        ('family:one',), ('operator:one',), 'b' * 64, 1, 'c' * 64, 'd' * 64,
        'e' * 64, True, True, 'fixture:salience-owner', '0' * 128))


def _lease():
    return issue_atlas_lease('fixture-lease', _run(), _scope(),
        ResourceCeiling(2, 2, 16384, 48 * 1024**3, 20 * 1024**3),
        requested_at=100, human_command_sha256='f' * 64, human_started=True,
        registry=_REGISTRY)


class AtlasLeaseTests(unittest.TestCase):
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

    def test_scope_signature_human_request_and_sets_fail_closed(self):
        for scope, human in ((replace(_scope(), signature_hex='0' * 128), True),
                             (_scope(), False), (_signed(replace(_scope(), audit_passed=False)), True),
                             (_signed(replace(_scope(), rights_compatible=False)), True)):
            with self.assertRaises(BilqisError):
                issue_atlas_lease('fixture-lease', _run(), scope, _lease().resource_ceiling,
                    requested_at=100, human_command_sha256='f' * 64, human_started=human,
                    registry=_REGISTRY)
        with self.assertRaises(BilqisError):
            replace(_scope(), source_family_ids=('same', 'same'))

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

    def test_lookup_only_scope_can_explicitly_allow_no_deterministic_operators(self):
        approval = _signed(replace(_scope(), operator_ids=()))
        lease = issue_atlas_lease('lookup-only', _run(), approval, _lease().resource_ceiling,
            requested_at=100, human_command_sha256='f' * 64, human_started=True, registry=_REGISTRY)
        self.assertEqual(lease.source_approval.operator_ids, ())
