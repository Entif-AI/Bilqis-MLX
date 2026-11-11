"""B13 create versus generic C07 fixture-writer serialization witnesses."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
import threading

from bilqis_mlx.errors import BilqisError
import bilqis_mlx.runtime._coordination as coordination
from bilqis_mlx.runtime.atlas_admission import persist_atlas_lease
from bilqis_mlx.runtime.atlas_lease_v2 import persist_atlas_lease_v2
from bilqis_mlx.runtime.tests._bamf_first_student_support import BamfFirstStudentCase
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import (
    _lease, _REGISTRY, _run,
)
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_lease_v2 import _lease_v2
from unittest.mock import patch


class BamfRootClaimRaceTests(BamfFirstStudentCase):
    def _race(self, version: str):
        target = self.root / ("race-" + version)
        target.mkdir()
        barrier = threading.Barrier(2)
        real_claim = coordination.run_root_claim

        @contextmanager
        def synchronized_claim(path: Path, *, create_parent: bool):
            barrier.wait(timeout=10)
            with real_claim(path, create_parent=create_parent):
                yield

        def b13():
            try:
                self.preflight(target)
                return "ok"
            except BilqisError as error:
                return error.context["reason"]

        def fixture():
            try:
                if version == "v1":
                    persist_atlas_lease(
                        target, _lease(), independently_loaded_run=_run(), registry=_REGISTRY)
                else:
                    persist_atlas_lease_v2(
                        target, _lease_v2(), independently_loaded_run=_run(),
                        registry=_REGISTRY)
                return "ok"
            except BilqisError as error:
                return error.context["reason"]

        with patch("bilqis_mlx.runtime._coordination.run_root_claim", synchronized_claim), \
                ThreadPoolExecutor(max_workers=2) as pool:
            b13_result = pool.submit(b13)
            fixture_result = pool.submit(fixture)
            results = (b13_result.result(), fixture_result.result())

        self.assertEqual(results.count("ok"), 1)
        current = target / "autonomy/atlas-admission"
        fixture_pointer = (
            current / "current.json" if version == "v1"
            else current / "v2/current.json")
        b13_pointer = target / "bamf-state.json"
        self.assertNotEqual(b13_pointer.exists(), fixture_pointer.exists())
        if results[0] == "ok":
            self.assertEqual(
                results[1], "BAMF_ATLAS_FIXTURE_AUTHORITY_FORBIDDEN_FOR_SAVED_RUN")
            self.assertTrue(b13_pointer.is_file())
        else:
            self.assertEqual(results[0], "BAMF_FIRST_STUDENT_RUN_DIRECTORY_OCCUPIED")
            self.assertTrue(fixture_pointer.is_file())
            self.assertFalse((target / ".bamf-pointer.lock").exists())
            self.assertFalse((target / "bamf-bundles").exists())

    def test_b13_create_serializes_against_v1_and_v2_fixture_writers(self):
        for version in ("v1", "v2"):
            with self.subTest(version=version):
                self._race(version)
