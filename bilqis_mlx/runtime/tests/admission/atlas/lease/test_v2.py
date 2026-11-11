"""Atlas lease v2 is a separate human authority epoch from historical v1."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import json
from pathlib import Path
import tempfile
from threading import Event
import unittest

from bilqis_mlx.runtime.atlas_admission import (
    _hold_current_atlas_lease_v2_publication,
    AtlasAdmissionLeaseV2,
    ResourceCeilingV2,
    issue_atlas_lease_v2,
    persist_atlas_lease,
    persist_atlas_lease_v2,
    read_atlas_lease_v2,
    renew_atlas_lease_v2,
)
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

    def test_publication_guard_serializes_human_renewal_until_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prior = _lease_v2()
            persist_atlas_lease_v2(
                root, prior, independently_loaded_run=_run(), registry=_REGISTRY)
            replacement = _lease_v2(
                lease_id="fixture-v2-renewed-race",
                requested_at="2026-11-10T18:00:00Z",
                command="7" * 64)
            started = Event()

            def renew():
                started.set()
                renew_atlas_lease_v2(
                    root, replacement,
                    independently_loaded_run=_run(), registry=_REGISTRY,
                    expected_prior_lease_sha256=prior.digest(), human_started=True)

            with ThreadPoolExecutor(max_workers=1) as workers:
                with _hold_current_atlas_lease_v2_publication(root, prior):
                    future = workers.submit(renew)
                    self.assertTrue(started.wait(1.0))
                    with self.assertRaises(TimeoutError):
                        future.result(timeout=0.05)
                    self.assertEqual(
                        read_atlas_lease_v2(root, _run(), registry=_REGISTRY), prior)
                future.result(timeout=2.0)

            self.assertEqual(
                read_atlas_lease_v2(root, _run(), registry=_REGISTRY), replacement)


if __name__ == "__main__":
    unittest.main()
