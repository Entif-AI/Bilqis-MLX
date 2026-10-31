"""BAMF architecture identity and historical isolation."""
from __future__ import annotations

import hashlib
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2, GenerationExtents, expected_bamf_shapes, initialize_bamf_parameter, initialize_bamf_row, initializer_seed, project_identity_source_factor


class InitializationTests(unittest.TestCase):
    @staticmethod
    def extents(banks=1, pages=1):
        return GenerationExtents(banks, pages, "a" * 64, "b" * 64, "c" * 64)

    def test_stable_initializer_seed(self):
        self.assertEqual(initializer_seed(0, "plastic.group.0.A"), 4633198684720072030)
        self.assertEqual(initializer_seed(0, "plastic.group.0.A"),
                         initializer_seed(0, "plastic.group.0.A", ""))
        self.assertNotEqual(initializer_seed(0, "identity.bank.0", "first"),
                            initializer_seed(0, "identity.bank.0", "second"))
        for seed in (True, 1.5):
            with self.assertRaises(BilqisError):
                initializer_seed(seed, "plastic.group.0.A")

    def test_independent_initializer_golden_and_linear_orientation(self):
        import numpy as np
        rows = {row.name: row for row in expected_bamf_shapes(ModelTopologySpecV2(), self.extents())}
        adapter = initialize_bamf_parameter(rows["plastic.group.0.A"], run_seed=0)
        self.assertEqual(hashlib.sha256(adapter.tobytes()).hexdigest(),
                         "8cd9500504ae983012b5463f193683f97eb62bec9a532b95e35dc51544a7c571")
        self.assertTrue(np.all(initialize_bamf_parameter(rows["plastic.group.0.B"], run_seed=0) == 0))
        convolution = initialize_bamf_parameter(rows["blocks.0.conv_q"], run_seed=0)
        np.testing.assert_array_equal(convolution[0], [0.0, 0.0, 1.0])
        self.assertTrue(np.all(initialize_bamf_parameter(rows["identity.bank.0"], run_seed=0) == 0))
        expected = {"blocks.0.query": 0.06222047284245491,
                    "blocks.0.key": 0.013152116909623146,
                    "blocks.0.value": 0.03874354809522629,
                    "blocks.0.output": -0.019073694944381714,
                    "blocks.0.ffn_in": -0.06427312642335892,
                    "blocks.0.ffn_out": 0.020128803327679634}
        for name, literal in expected.items():
            weight = initialize_bamf_parameter(rows[name], run_seed=0)
            basis = np.zeros(weight.shape[1], dtype=np.float32)
            basis[5] = 1.0
            self.assertEqual(float((basis @ weight.T)[3]), literal, name)

    def test_row_initializers_are_stable_across_bank_growth(self):
        import numpy as np
        spec = ModelTopologySpecV2()
        first = {item.name: item for item in expected_bamf_shapes(spec, self.extents())}
        grown = {item.name: item for item in expected_bamf_shapes(spec, self.extents(banks=2, pages=2))}
        factors = np.ones(768, dtype=np.float32)
        identity = initialize_bamf_row(first["identity.bank.0"], run_seed=0,
                                       row_id="fixture:identity", factor=factors)
        self.assertEqual(hashlib.sha256(identity.tobytes()).hexdigest(),
                         "1c8fd2c39a4fac159fcdd9d54660bb0ee8b8dd256a77469b36763749ee8d2a79")
        np.testing.assert_array_equal(identity, initialize_bamf_row(grown["identity.bank.0"], run_seed=0,
                                                                    row_id="fixture:identity", factor=factors))
        motif = initialize_bamf_row(first["motif.page.0"], run_seed=0, row_id="fixture:motif")
        self.assertEqual(hashlib.sha256(motif.tobytes()).hexdigest(),
                         "2362325203db3fbd9d2a064cb6eec7aa6feff834ec8e16cad7aadc0a6b9e69fe")
        np.testing.assert_array_equal(motif, initialize_bamf_row(grown["motif.page.0"], run_seed=0,
                                                                 row_id="fixture:motif"))
        with self.assertRaises(BilqisError):
            initialize_bamf_row(first["identity.bank.0"], run_seed=0, row_id="fixture:identity")

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
