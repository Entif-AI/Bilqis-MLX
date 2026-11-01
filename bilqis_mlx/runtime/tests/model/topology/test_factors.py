"""B01 factors conformance and compatibility."""
from bilqis_mlx.runtime.tests.model.topology.helpers import (
    BilqisError,
    TopologyFixture,
    project_identity_source_factor,
)


class TopologyFactorsTests(TopologyFixture):
    def test_source_bound_identity_factor_projection_is_b02_independent(self):
        import mlx.core as mx
        import numpy as np

        type_table = mx.zeros((512, 128), dtype=mx.float32)
        type_table = type_table.at[2].add(mx.ones((128,), dtype=mx.float32))
        parameters = {
            "features.type": type_table,
            "features.project_type": mx.ones((768, 128), dtype=mx.float32) / 128.0,
            "features.project_graph": mx.concatenate((
                mx.full((768, 1), 2.0, dtype=mx.float32),
                mx.zeros((768, 63), dtype=mx.float32)), axis=1),
            "features.gates": mx.zeros((4,), dtype=mx.float32),
        }
        factor = project_identity_source_factor(
            parameters, type_rows=(2,), type_overflow=(None,),
            graph64=(1.0,) + (0.0,) * 63,
            extents=self.extents(), predecessor_feature_digest="c" * 64)
        self.assertEqual(factor.shape, (768,))
        self.assertEqual(factor.dtype, np.float32)
        np.testing.assert_allclose(factor, np.full((768,), 1.5, dtype=np.float32))
        with self.assertRaises(BilqisError):
            project_identity_source_factor(
                parameters, type_rows=(2,), type_overflow=(None,),
                graph64=(1.0,) + (0.0,) * 63,
                extents=self.extents(), predecessor_feature_digest="d" * 64)
