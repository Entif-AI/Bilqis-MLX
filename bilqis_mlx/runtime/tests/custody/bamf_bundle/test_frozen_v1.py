"""Opt-in read-only witness using an externally pinned historical whole student.

BILQIS_FROZEN_V1_BUNDLE and BILQIS_FROZEN_V1_MANIFEST_SHA256 select the archive.
Without both, this acceptance witness is explicitly unmeasured. No fixture is
substituted for the genuine archive, and no optimizer update is executed.
"""
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.data_plane import data_plane
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.bamf_bundle import load_bamf_bundle
from bilqis_mlx.runtime.model_topology import CURRENT_DEFAULT_TOPOLOGY, validate_parameter_shapes
from bilqis_mlx.runtime.model_topology_v2 import BAMF_ARCHITECTURE_ID, ModelTopologySpecV2
from bilqis_mlx.runtime.topology_lifecycle import dispatch_model_factory


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class FrozenV1Tests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, {
            "BILQIS_DATA_PLANE": str(Path(temporary.name) / "plane.db")})
        environment.start()
        self.addCleanup(environment.stop)

    def test_pinned_six_layer_archive_reads_without_v2_allocation_or_mutation(self):
        selected = os.environ.get('BILQIS_FROZEN_V1_BUNDLE')
        pinned = os.environ.get('BILQIS_FROZEN_V1_MANIFEST_SHA256')
        if not selected or not pinned:
            self.skipTest('NOT_MEASURED: externally pinned historical-v1 archive required')
        root = Path(selected)
        self.assertEqual(file_digest(root / 'manifest.json'), pinned)
        before = {p.name: file_digest(p) for p in root.iterdir() if p.is_file()}
        device = mx.default_device()
        try:
            mx.set_default_device(mx.cpu)
            parameters, optimizer, manifest, catalog = mlx_checkpoint.load_semantically_bound_bundle(root)
            self.assertEqual(manifest['schema'], mlx_checkpoint.SCHEMA)
            self.assertEqual(CURRENT_DEFAULT_TOPOLOGY.layers, 6)
            validate_parameter_shapes(parameters, CURRENT_DEFAULT_TOPOLOGY, len(catalog['tokens']))
            self.assertIn('position.weight', parameters)
            self.assertEqual(int(optimizer.state['step'].item()), manifest['optimizer_step'])
            self.assertEqual(set(optimizer.state), {'step', 'learning_rate', *parameters})
            for name, value in parameters.items():
                self.assertEqual(value.dtype, mx.float32)
                self.assertEqual(optimizer.state[name]['m'].shape, value.shape)
                self.assertEqual(optimizer.state[name]['v'].shape, value.shape)
            # Index genuine bytes only in this test's isolated data plane.
            # Rejection must survive node availability, not merely a missing node.
            data_plane().put_node(pinned, (root / 'manifest.json').read_bytes(), 0, None)
            with patch.object(mlx_checkpoint, 'load_bamf_state_payload',
                              side_effect=AssertionError('v2 tensor construction reached')):
                with self.assertRaises(BilqisError):
                    load_bamf_bundle(root)
            def forbidden_factory(_):
                self.fail('v1 bytes reached a model/optimizer factory')
            with self.assertRaises(BilqisError):
                dispatch_model_factory(
                    BAMF_ARCHITECTURE_ID, ModelTopologySpecV2().to_record(),
                    legacy_factory=forbidden_factory, bamf_factory=forbidden_factory,
                    checkpoint_path=root)
        finally:
            mx.set_default_device(device)
            self.assertEqual({p.name: file_digest(p) for p in root.iterdir() if p.is_file()}, before)


if __name__ == '__main__':
    unittest.main()
