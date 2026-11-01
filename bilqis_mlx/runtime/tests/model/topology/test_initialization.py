"""B01 initialization conformance and compatibility."""
from bilqis_mlx.runtime.tests.model.topology.helpers import (
    BilqisError,
    ModelTopologySpecV2,
    TopologyFixture,
    expected_bamf_shapes,
    hashlib,
    initialize_bamf_parameter,
    initialize_bamf_row,
)


class TopologyInitializationTests(TopologyFixture):
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
