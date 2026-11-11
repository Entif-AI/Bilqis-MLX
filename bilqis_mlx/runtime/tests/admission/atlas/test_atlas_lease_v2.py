"""Atlas lease v2 is a separate human authority epoch from historical v1."""
from dataclasses import asdict, replace
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError

from bilqis_mlx.runtime.atlas_admission import (
    AtlasAdmissionEnrollmentRequestV2,
    AtlasAdmissionLeaseV2,
    ResourceCeilingV2,
    enroll_accepted_atlas_lease_v2,
    issue_atlas_lease_v2,
    persist_accepted_atlas_lease_v2,
    persist_atlas_lease,
    persist_atlas_lease_v2,
    read_atlas_lease_v2,
    renew_atlas_lease_v2,
)
import bilqis_mlx.runtime.atlas_lease_storage_v2 as lease_storage_v2
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import (
    _REGISTRY, _lease, _run, _scope,
)


def _lease_v2(*, lease_id="fixture-v2", requested_at="2026-11-10T16:00:00Z",
              command="9" * 64):
    return issue_atlas_lease_v2(
        lease_id, _run(), _scope(),
        ResourceCeilingV2(4, 4, 32768, 64 * 1024**3, 160 * 1024**3),
        requested_at=requested_at, human_command_sha256=command,
        human_started=True, registry=_REGISTRY)


class AtlasLeaseV2Tests(unittest.TestCase):
    def test_typed_equal_but_byte_different_orphan_is_immutable_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lease = _lease_v2()
            lease_dir = root / 'autonomy/atlas-admission/v2/leases'
            lease_dir.mkdir(parents=True)
            orphan = lease_dir / (lease.digest() + '.json')
            # Semantically identical JSON, intentionally not the durable writer bytes.
            raw = json.dumps(asdict(lease), sort_keys=True, separators=(',', ':')).encode()
            orphan.write_bytes(raw)

            with self.assertRaises(BilqisError) as raised:
                persist_atlas_lease_v2(
                    root, lease, independently_loaded_run=_run(), registry=_REGISTRY)

            self.assertEqual(
                raised.exception.context.get('reason'),
                'BAMF_ATLAS_LEASE_V2_IMMUTABLE_DRIFT')
            self.assertEqual(orphan.read_bytes(), raw)
            self.assertFalse((root / 'autonomy/atlas-admission/v2/current.json').exists())

    def test_post_reference_readback_uncertainty_reconciles_exact_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lease = _lease_v2()
            real_read = lease_storage_v2._read_atlas_lease_v2
            calls = 0

            def uncertain_once(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    return None
                if calls == 2:
                    from bilqis_mlx.runtime.atlas_lease_contracts import _invalid
                    _invalid('BAMF_ATLAS_LEASE_V2_READ_FAILED')
                return real_read(*args, **kwargs)

            with patch.object(lease_storage_v2, '_read_atlas_lease_v2',
                              side_effect=uncertain_once):
                reference = persist_atlas_lease_v2(
                    root, lease, independently_loaded_run=_run(), registry=_REGISTRY)

            self.assertEqual(
                reference, root / 'autonomy/atlas-admission/v2/current.json')
            self.assertEqual(
                read_atlas_lease_v2(root, _run(), registry=_REGISTRY), lease)

    def test_v2_persists_separately_without_reinterpreting_v1_current(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            v1 = _lease()
            persist_atlas_lease(
                root, v1, independently_loaded_run=_run(), registry=_REGISTRY)
            v1_reference = root / "autonomy/atlas-admission/current.json"
            before = v1_reference.read_bytes()

            v2 = _lease_v2()
            reference = persist_atlas_lease_v2(
                root, v2, independently_loaded_run=_run(), registry=_REGISTRY)

            self.assertIsInstance(v2, AtlasAdmissionLeaseV2)
            self.assertEqual(reference, root / "autonomy/atlas-admission/v2/current.json")
            self.assertEqual(v1_reference.read_bytes(), before)
            self.assertEqual(
                read_atlas_lease_v2(root, _run(), registry=_REGISTRY), v2)
            payload = json.loads(reference.read_text())
            self.assertEqual(payload["schema"], "bilqis.c07.atlas-lease-reference/v2")
            self.assertTrue(payload["lease_file"].startswith(
                "autonomy/atlas-admission/v2/leases/"))

    def test_v2_renewal_is_explicit_and_preserves_v1_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            persist_atlas_lease(
                root, _lease(), independently_loaded_run=_run(), registry=_REGISTRY)
            v1_reference = root / "autonomy/atlas-admission/current.json"
            before = v1_reference.read_bytes()
            prior = _lease_v2()
            persist_atlas_lease_v2(
                root, prior, independently_loaded_run=_run(), registry=_REGISTRY)
            replacement = _lease_v2(
                lease_id="fixture-v2-renewed",
                requested_at="2026-11-10T17:00:00Z",
                command="8" * 64)

            renew_atlas_lease_v2(
                root, replacement, independently_loaded_run=_run(), registry=_REGISTRY,
                expected_prior_lease_sha256=prior.digest(), human_started=True)

            self.assertEqual(
                read_atlas_lease_v2(root, _run(), registry=_REGISTRY), replacement)
            self.assertEqual(v1_reference.read_bytes(), before)

    def test_accepted_v2_persistence_rejects_existing_v1_authority(self):
        with tempfile.TemporaryDirectory() as temporary, patch(
                'bilqis_mlx.runtime.atlas_admission._accepted_run_lease_identity',
                return_value=_run()), patch(
                'bilqis_mlx.runtime.atlas_admission._accepted_source_registry',
                return_value=_REGISTRY):
            root = Path(temporary)
            v1 = root / 'autonomy/atlas-admission/current.json'
            v1.parent.mkdir(parents=True)
            v1.write_text('{}')
            with self.assertRaises(BilqisError) as failure:
                persist_accepted_atlas_lease_v2(
                    root, _lease_v2(), source_authority=object())
            self.assertEqual(
                failure.exception.context['reason'],
                'BAMF_ATLAS_V2_LEGACY_AUTHORITY_PRESENT')
            self.assertFalse(
                (root / 'autonomy/atlas-admission/v2/current.json').exists())

    def _enrollment_request(self, *, run_id='accepted-run', run_seed=19,
                            topology='a' * 64, release=None):
        approval = _scope()
        if release is not None:
            approval = replace(approval, atlas_release_sha256=release)
        return AtlasAdmissionEnrollmentRequestV2(
            'accepted-v2', run_id, run_seed, topology, approval,
            _lease_v2().resource_ceiling, '2026-11-11T03:00:00Z', '7' * 64)

    def test_enrollment_owner_does_not_duplicate_presentation_epoch_precheck(self):
        identity = SimpleNamespace(
            run_id='accepted-run', run_seed=19,
            initial_topology_digest='a' * 64,
            initial_release_digest=_scope().atlas_release_sha256)
        with tempfile.TemporaryDirectory() as temporary, patch(
                'bilqis_mlx.runtime.bamf_bundle.load_bamf_generation_authority',
                return_value=(SimpleNamespace(run_identity=identity), 'b' * 64)), patch(
                'bilqis_mlx.runtime.bamf_bundle.read_accepted_generation_feature_receipt',
                return_value=SimpleNamespace(
                    source_release_sha256=identity.initial_release_digest)), patch(
                'bilqis_mlx.runtime.atlas_admission._accepted_run_lease_identity',
                return_value=_run()), patch(
                'bilqis_mlx.runtime.atlas_admission._accepted_source_registry',
                side_effect=AssertionError('C09 must not run')):
            root = Path(temporary)
            v1 = root / 'autonomy/atlas-admission/current.json'
            v1.parent.mkdir(parents=True)
            v1.write_text('{}')
            with self.assertRaisesRegex(AssertionError, 'C09 must not run'):
                enroll_accepted_atlas_lease_v2(
                    root, self._enrollment_request(), human_started=True,
                    source_authority=object())

    def test_enrollment_identity_mismatch_precedes_release_and_c09(self):
        identity = SimpleNamespace(
            run_id='accepted-run', run_seed=19,
            initial_topology_digest='a' * 64,
            initial_release_digest=_scope().atlas_release_sha256)
        with tempfile.TemporaryDirectory() as temporary, patch(
                'bilqis_mlx.runtime.bamf_bundle.load_bamf_generation_authority',
                return_value=(SimpleNamespace(run_identity=identity), 'b' * 64)), patch(
                'bilqis_mlx.runtime.bamf_bundle.read_accepted_generation_feature_receipt',
                return_value=SimpleNamespace(
                    source_release_sha256=identity.initial_release_digest)), patch(
                'bilqis_mlx.runtime.atlas_admission._accepted_source_registry',
                side_effect=AssertionError('C09 must not run')):
            with self.assertRaises(BilqisError) as failure:
                enroll_accepted_atlas_lease_v2(
                    Path(temporary),
                    self._enrollment_request(
                        run_id='wrong-run', release='f' * 64),
                    human_started=True, source_authority=object())
            self.assertEqual(
                failure.exception.context['reason'],
                'BAMF_ATLAS_V2_ENROLLMENT_RUN_IDENTITY_DRIFT')

    def test_enrollment_owner_converges_exact_v2_lease(self):
        identity = SimpleNamespace(
            run_id='accepted-run', run_seed=19,
            initial_topology_digest='a' * 64,
            initial_release_digest=_scope().atlas_release_sha256)
        with tempfile.TemporaryDirectory() as temporary, patch(
                'bilqis_mlx.runtime.bamf_bundle.load_bamf_generation_authority',
                return_value=(SimpleNamespace(run_identity=identity), 'b' * 64)), patch(
                'bilqis_mlx.runtime.bamf_bundle.read_accepted_generation_feature_receipt',
                return_value=SimpleNamespace(
                    source_release_sha256=identity.initial_release_digest)), patch(
                'bilqis_mlx.runtime.atlas_admission._accepted_run_lease_identity',
                return_value=_run()), patch(
                'bilqis_mlx.runtime.atlas_admission._accepted_source_registry',
                return_value=_REGISTRY):
            root = Path(temporary)
            lease = enroll_accepted_atlas_lease_v2(
                root, self._enrollment_request(), human_started=True,
                source_authority=object())
            self.assertEqual(
                read_atlas_lease_v2(root, _run(), registry=_REGISTRY), lease)


if __name__ == "__main__":
    unittest.main()
