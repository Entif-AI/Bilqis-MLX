"""The CAS reserve decision and copy share cross-process serialization."""
import multiprocessing
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import bilqis_mlx.runtime.bamf_bundle.codec as codec
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.runtime.disk import assert_headroom
import bilqis_mlx.runtime.disk as disk
from bilqis_mlx.data_plane import data_plane
from bilqis_mlx.runtime.tests.custody.data_plane.base import DataPlaneCase
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state, candidate, parent_state, shape_patch,
)


def reserve_worker(root, changed, barrier, results):
    plane = data_plane()
    source = parent_state()
    if changed:
        source = accepted_state(source)

    def reserve(path, *, required_bytes, reserve_gib=100.0):
        unittest.TestCase().assertTrue(plane._db.in_transaction,
                                       "CAS reserve checked outside writer transaction")
        used = sum(p.stat().st_size for p in Path(root).glob("plane.sqlite3.objects/*/*.safetensors"))
        free = int(reserve_gib * 1024**3) + required_bytes - used
        with patch.object(disk.shutil, "disk_usage", return_value=SimpleNamespace(free=free)):
            return assert_headroom(path, required_bytes=required_bytes, reserve_gib=reserve_gib)

    try:
        barrier.wait(timeout=15)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom",
                             side_effect=lambda *args, **kwargs: unittest.TestCase().assertTrue(plane._db.in_transaction)), \
                patch.object(codec, "assert_headroom", side_effect=reserve):
            codec.save_bamf_bundle(candidate(source), Path(root) / str(changed))
        results.put("OK")
    except RuntimeError as error:
        results.put("RESERVE" if str(error) == "DISK_BUDGET_EXHAUSTED" else repr(error))
    except Exception as error:
        results.put(repr(error))


class TensorReserveConcurrencyTests(DataPlaneCase):
    def test_concurrent_distinct_objects_recheck_one_copy_budget(self):
        from bilqis_mlx.runtime.tests.custody.bamf_bundle.test_tensor_reserve_concurrency import (
            reserve_worker as process_target,
        )
        data_plane()
        context = multiprocessing.get_context("spawn")
        barrier, results = context.Barrier(2), context.Queue()
        workers = [context.Process(target=process_target,
                                   args=(str(self.root), changed, barrier, results))
                   for changed in (False, True)]
        try:
            for worker in workers:
                worker.start()
            self.assertEqual(sorted(results.get(timeout=25) for unused in workers),
                             ["OK", "RESERVE"])
            for worker in workers:
                worker.join(timeout=5)
                self.assertEqual(worker.exitcode, 0)
            self.assertEqual(len(tuple(self.root.glob("plane.sqlite3.objects/*/*.safetensors"))), 1)
        finally:
            for worker in workers:
                if worker.is_alive():
                    worker.terminate()
                    worker.join()
            results.close()
