"""C07 accepted v1/v2 cross-epoch serialization witnesses for C16.1a."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_admission import persist_accepted_atlas_lease
from bilqis_mlx.runtime.atlas_lease_storage import classify_accepted_atlas_epoch
from bilqis_mlx.runtime.atlas_lease_v2 import persist_accepted_atlas_lease_v2
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_admission import (
    _lease, _REGISTRY, _run,
)
from bilqis_mlx.runtime.tests.admission.atlas.test_atlas_lease_v2 import _lease_v2


class AtlasEpochSerializationTests(unittest.TestCase):
    def _accepted_context(self):
        return (
            patch("bilqis_mlx.runtime.atlas_admission._accepted_run_lease_identity",
                  return_value=_run()),
            patch("bilqis_mlx.runtime.atlas_admission._accepted_source_registry",
                  return_value=_REGISTRY),
        )

    def _write(self, root: Path, version: str, barrier=None):
        if barrier is not None:
            barrier.wait()
        try:
            if version == "v1":
                persist_accepted_atlas_lease(root, _lease(), source_authority=object())
            else:
                persist_accepted_atlas_lease_v2(
                    root, _lease_v2(), source_authority=object())
            return "ok"
        except BilqisError as error:
            return error.context["reason"]

    def test_sequential_cross_epoch_mutation_rejects_second_writer_both_orders(self):
        for first, second, expected in (
                ("v1", "v2", "BAMF_ATLAS_V2_LEGACY_AUTHORITY_PRESENT"),
                ("v2", "v1", "BAMF_ATLAS_V1_SUCCESSOR_AUTHORITY_PRESENT")):
            with self.subTest(order=(first, second)), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                c1, c2 = self._accepted_context()
                with c1, c2:
                    self.assertEqual(self._write(root, first), "ok")
                    self.assertEqual(self._write(root, second), expected)
                self.assertEqual(classify_accepted_atlas_epoch(root), first)

    def test_synchronized_cross_epoch_race_allows_exactly_one_authority_epoch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            barrier = threading.Barrier(2)
            c1, c2 = self._accepted_context()
            with c1, c2, ThreadPoolExecutor(max_workers=2) as pool:
                results = tuple(pool.map(
                    lambda version: self._write(root, version, barrier), ("v1", "v2")))
            self.assertEqual(results.count("ok"), 1)
            self.assertEqual(classify_accepted_atlas_epoch(root),
                             "v1" if results[0] == "ok" else "v2")
            self.assertTrue(any(reason in {
                "BAMF_ATLAS_V2_LEGACY_AUTHORITY_PRESENT",
                "BAMF_ATLAS_V1_SUCCESSOR_AUTHORITY_PRESENT",
            } for reason in results if reason != "ok"))


if __name__ == "__main__":
    unittest.main()
