"""B13 create versus generic C07 fixture-writer serialization witnesses."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
import threading

from bilqis_mlx.errors import BilqisError
import bilqis_mlx.runtime._coordination as coordination
from bilqis_mlx.runtime.atlas_admission import persist_atlas_lease, renew_atlas_lease
from bilqis_mlx.runtime.atlas_lease_v2 import persist_atlas_lease_v2, renew_atlas_lease_v2
from bilqis_mlx.runtime.tests._bamf_first_student_support import BamfFirstStudentCase
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import (
    _lease, _REGISTRY, _run,
)
from bilqis_mlx.runtime.tests.admission.atlas.lease.test_v2 import _lease_v2
from unittest.mock import patch
from dataclasses import replace
import os
import unicodedata


class BamfRootClaimRaceTests(BamfFirstStudentCase):
    def _race(self, version: str, *, b13_target=None, fixture_target=None):
        target = Path(b13_target or (self.root / ("race-" + version)))
        if not target.exists():
            target.mkdir()
        fixture_target = Path(fixture_target or target)
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
                        fixture_target, _lease(), independently_loaded_run=_run(), registry=_REGISTRY)
                else:
                    persist_atlas_lease_v2(
                        fixture_target, _lease_v2(), independently_loaded_run=_run(),
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

    def test_accepted_generation_zero_blocks_all_generic_fixture_entrypoints(self):
        target = self.root / "accepted-root"
        self.preflight(target)
        before = tuple((str(path.relative_to(target)), path.read_bytes())
                       for path in sorted(target.rglob("*")) if path.is_file())
        v1 = _lease()
        v2 = _lease_v2()
        operations = (
            lambda: persist_atlas_lease(
                target, v1, independently_loaded_run=_run(), registry=_REGISTRY),
            lambda: renew_atlas_lease(
                target, replace(v1, lease_id="renewed-v1", requested_at=101,
                                human_command_sha256="8" * 64),
                independently_loaded_run=_run(), registry=_REGISTRY,
                expected_prior_lease_sha256=v1.digest(), human_started=True),
            lambda: persist_atlas_lease_v2(
                target, v2, independently_loaded_run=_run(), registry=_REGISTRY),
            lambda: renew_atlas_lease_v2(
                target, _lease_v2(lease_id="renewed-v2",
                                  requested_at="2026-11-10T17:00:00Z",
                                  command="8" * 64),
                independently_loaded_run=_run(), registry=_REGISTRY,
                expected_prior_lease_sha256=v2.digest(), human_started=True),
        )
        for operation in operations:
            with self.subTest(operation=operation), self.assertRaises(BilqisError) as failure:
                operation()
            self.assertEqual(
                failure.exception.context["reason"],
                "BAMF_ATLAS_FIXTURE_AUTHORITY_FORBIDDEN_FOR_SAVED_RUN")
        after = tuple((str(path.relative_to(target)), path.read_bytes())
                      for path in sorted(target.rglob("*")) if path.is_file())
        self.assertEqual(after, before)
        self.assertFalse((target / "autonomy").exists())

    def test_physical_aliases_share_the_same_root_claim_when_host_exposes_them(self):
        probe_case = self.root / "Case-Probe"
        probe_case.mkdir()
        case_supported = (self.root / "case-probe").exists()
        probe_unicode = self.root / "caf\u00e9-probe"
        probe_unicode.mkdir()
        unicode_supported = (
            self.root / unicodedata.normalize("NFD", probe_unicode.name)).exists()
        if not case_supported and not unicode_supported:
            self.skipTest("host filesystem exposes no case/Unicode physical alias")
        for version in ("v1", "v2"):
            if case_supported:
                primary = self.root / f"Race-{version}"
                primary.mkdir()
                alias = self.root / f"race-{version}"
                self.assertTrue(os.path.samefile(primary, alias))
                with self.subTest(alias="case", version=version):
                    self._race(version, b13_target=primary, fixture_target=alias)
            if unicode_supported:
                primary = self.root / f"caf\u00e9-{version}"
                primary.mkdir()
                alias = self.root / unicodedata.normalize("NFD", primary.name)
                self.assertTrue(os.path.samefile(primary, alias))
                with self.subTest(alias="unicode", version=version):
                    self._race(version, b13_target=primary, fixture_target=alias)
