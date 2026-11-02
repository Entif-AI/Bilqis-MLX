"""C12 delta identity comes from the current B13 generation."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import os

import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.bamf_bundle import publish_bamf_generation, publication
from bilqis_mlx.runtime.cognitive_package import (
    DeltaSlice, PackageArtifact, PackageBinding, PackageKind, ReceiverTensor,
    apply_plastic_delta, encode_plastic_delta, export_capability,
    receiver_parameter_schema_digest, receiver_weight_digest,
)
from bilqis_mlx.runtime.cognitive_package.tests.fixtures import snapshot
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    NAME, candidate, parent_state, shape_patch,
)


class ReceiverCustodyTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'BILQIS_DATA_PLANE': str(self.root / 'plane.sqlite3')})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.run = self.root / 'run'
        self.student = candidate(parent_state())
        with shape_patch(), patch.object(mlx_checkpoint, 'assert_headroom'):
            self.pointer = publish_bamf_generation(self.run, self.student)
        array = np.asarray(self.student.retained_state.optimizer.parameters[NAME], dtype='<f4')
        self.tensor = ReceiverTensor(NAME, array.shape, array.tobytes())
        self.binding = PackageBinding(
            receiver_weight_digest((self.tensor,)), receiver_parameter_schema_digest((self.tensor,)),
            self.student.topology.digest, self.student.provenance.release_digest,
            self.student.extents.active_semantic_digest, self.student.extents.factor_map_digest,
            self.student.extents.motif_key_map_digest)

    def package(self, binding):
        source, rights = snapshot(PackageKind.WEIGHT_DELTA)
        parent = np.frombuffer(self.tensor.values_fp32, dtype='<f4')
        delta = np.asarray([.5], dtype='<f4').tobytes()
        artifact = PackageArtifact('weights', PackageKind.WEIGHT_DELTA,
            encode_plastic_delta((DeltaSlice(NAME, 0, 1, sha256(parent[:1].tobytes()).hexdigest(), delta),)))
        source = replace(source, binding=binding, artifacts=(artifact,) + source.artifacts[1:])
        rights = replace(rights, public_artifact_digests=tuple(sorted(a.digest for a in source.artifacts)))
        return export_capability(source, source.signature, rights)

    def test_current_pointer_is_the_parent_of_a_compatible_candidate(self):
        with shape_patch():
            result = apply_plastic_delta(self.package(self.binding), self.run)
        self.assertEqual(result.parent_generation, self.pointer['manifest_sha256'])
        self.assertEqual(result.binding, self.binding)
        self.assertEqual(np.frombuffer(result.tensors[0].values_fp32, dtype='<f4')[0], 1.)

    def test_forged_matching_motif_and_arbitrary_parent_cannot_authorize(self):
        forged = replace(self.binding, motif_key_map_digest='1' * 64)
        package = self.package(forged)
        with shape_patch(), self.assertRaises(BilqisError):
            apply_plastic_delta(package, self.run)
        with self.assertRaises((TypeError, BilqisError)):
            apply_plastic_delta(package, forged, '2' * 64, (self.tensor,))

    def test_each_non_tensor_binding_is_derived_from_current_generation(self):
        for field in ('topology_digest', 'semantic_release', 'active_set_digest',
                      'factor_map_digest', 'motif_key_map_digest'):
            with self.subTest(field=field), shape_patch(), self.assertRaises(BilqisError):
                apply_plastic_delta(self.package(replace(self.binding, **{field: '1' * 64})), self.run)

    def test_active_pointer_lock_refuses_concurrent_apply(self):
        with publication._pointer_lock(self.run), shape_patch(), self.assertRaises(BilqisError):
            apply_plastic_delta(self.package(self.binding), self.run)
