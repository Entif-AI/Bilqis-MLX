"""B13.3 disposable inference state stays outside durable learning custody."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.bamf_bundle import load_bamf_bundle, save_bamf_bundle
from bilqis_mlx.runtime.bamf_bundle.records import SIDECARS
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, parent_state, shape_patch,
)


class CacheSeparationTests(unittest.TestCase):
    def setUp(self):
        device = mx.default_device()
        mx.set_default_device(mx.cpu)
        self.addCleanup(mx.set_default_device, device)

    def test_cache_loss_or_corruption_does_not_change_cold_learning_state(self):
        with TemporaryDirectory() as tmp, patch.dict(
                os.environ, {'BILQIS_DATA_PLANE': str(Path(tmp) / 'plane.db')}):
            root = Path(tmp) / 'bundle'
            source = candidate(parent_state())
            with shape_patch(), patch.object(mlx_checkpoint, 'assert_headroom'):
                manifest = save_bamf_bundle(source, root)
                self.assertEqual(set(p.name for p in root.iterdir()),
                                 {'manifest.json', 'bamf-state.safetensors', *SIDECARS.values()})
                immutable = {p.name: p.read_bytes() for p in root.iterdir()}
                cache = root / 'inference-cache.bin'
                cache.write_bytes(b'corrupt disposable inference state')
                for cache_present in (True, False):
                    if not cache_present:
                        cache.unlink()
                    with self.subTest(cache_present=cache_present):
                        restored = load_bamf_bundle(
                            root, expected_manifest_sha256=manifest['manifest_sha256'])
                        expected = source.retained_state
                        actual = restored.retained_state
                        for part in ('parameters', 'm', 'v', 'update_counts'):
                            for name, value in getattr(expected.optimizer, part).items():
                                np.testing.assert_array_equal(
                                    np.asarray(value), np.asarray(getattr(actual.optimizer, part)[name]))
                        self.assertEqual(actual.optimizer_step, expected.optimizer_step)
                        self.assertEqual(actual.policy, expected.policy)
                        self.assertEqual(restored.teacher_state, source.teacher_state)
                        self.assertEqual(restored.semantic_abi, source.semantic_abi)
                        self.assertEqual(restored.compiler_features, source.compiler_features)
                        self.assertEqual(restored.correction_frontier, source.correction_frontier)
                        self.assertEqual(restored.evaluation_contract, source.evaluation_contract)
                        self.assertEqual(restored.retained_state.allocations,
                                         source.retained_state.allocations)
                        self.assertEqual({name: (root / name).read_bytes() for name in immutable},
                                         immutable)
                self.assertFalse(cache.exists())


if __name__ == '__main__':
    unittest.main()
