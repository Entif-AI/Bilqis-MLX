"""BAMF architecture identity and historical isolation."""
from __future__ import annotations

import json
import hashlib
from contextlib import redirect_stdout
from io import StringIO
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology import ModelTopologySpec
from bilqis_mlx.runtime.model_topology_v2 import (
    BAMF_ARCHITECTURE_ID, LEGACY_ARCHITECTURE_ID, ModelTopologySpecV2,
    GenerationExtents, GenerationProvenance, ParameterCategory, ParameterCensus, ParameterGroup, ParameterSpec, Initializer,
    bamf_parameter_census, print_bamf_parameter_census,
    bamf_deserialize_arrays, bamf_serialization_arrays, bamf_storage_key,
    deserialize_topology,
    expected_bamf_shapes, initialize_bamf_parameter, initialize_bamf_row, initializer_seed,
    project_identity_source_factor,
    validate_bamf_parameters,
)
from bilqis_mlx.runtime.topology_lifecycle import (
    construct_unbound_model, dispatch_model_factory, operator_topology, topology_from_file,
)


from bilqis_mlx.runtime.tests.model.topology.helpers import ModelTopologyFixture, PROJECT_ROOT

class ModelTopologyV2Tests(ModelTopologyFixture):
    def test_stable_initializer_seed(self):
        self.assertEqual(initializer_seed(0, "plastic.group.0.A"), 4633198684720072030)
        self.assertEqual(initializer_seed(0, "plastic.group.0.A"),
                         initializer_seed(0, "plastic.group.0.A", ""))
        self.assertNotEqual(initializer_seed(0, "identity.bank.0", "first"),
                            initializer_seed(0, "identity.bank.0", "second"))
        for seed in (True, 1.5):
            with self.assertRaises(BilqisError):
                initializer_seed(seed, "plastic.group.0.A")

    def test_literal_tensor_ledger_and_extents(self):
        spec = ModelTopologySpecV2()
        rows = expected_bamf_shapes(spec, self.extents())
        by_name = {row.name: row for row in rows}
        self.assertEqual(len(by_name), len(rows))
        literal_shapes = {
            "blocks.0.query": (384, 768), "blocks.0.key": (192, 768),
            "blocks.0.value": (192, 768), "blocks.0.output": (768, 384),
            "blocks.0.ffn_in": (3072, 768), "blocks.0.ffn_out": (768, 3072),
            "identity.bank.0": (8192, 768), "motif.page.0": (16384, 128),
            "plastic.group.0.A": (8, 768), "plastic.group.0.B": (768, 8),
        }
        for name, shape in literal_shapes.items():
            self.assertEqual(by_name[name].shape, shape)
            self.assertEqual(by_name[name].dtype, "float32")
        self.assertEqual(sum(math.prod(by_name[f"blocks.{i}.{part}"].shape)
            for i in range(12) for part in ("query", "key", "value", "output", "ffn_in", "ffn_out")),
            67239936)
        grown = {row.name: row for row in expected_bamf_shapes(spec, self.extents(banks=2))}
        self.assertEqual(grown["identity.bank.0"], by_name["identity.bank.0"])
        self.assertEqual(grown["identity.bank.1"].shape, (8192, 768))
        self.assertNotEqual(self.extents().digest, self.extents(banks=2).digest)
        self.assertNotEqual(self.extents().digest, self.extents(pages=2).digest)
        self.assertEqual(spec.digest, ModelTopologySpecV2().digest)

    def test_parameter_census_reconciles_literal_counts_and_capacities(self):
        spec = ModelTopologySpecV2()
        census = bamf_parameter_census(spec, self.extents())
        self.assertEqual(census.total, 79469798)
        self.assertEqual(census.subtotals, {
            ParameterCategory.DENSE_MATRICES: 67239936,
            ParameterCategory.SEMANTIC_TABLES: 6291456,
            ParameterCategory.MOTIF_TABLES: 2097152,
            ParameterCategory.ADAPTER_MATRICES: 36864,
            ParameterCategory.AUXILIARY: 3804390,
        })
        self.assertEqual(sum(census.subtotals.values()), census.total)
        rows = {item.name: item for item in census.parameters}
        self.assertEqual(len(rows), 214)
        for kind in ("type", "role", "schema"):
            self.assertEqual(rows[f"features.{kind}"].shape, (512, 128))
            self.assertEqual(rows[f"features.{kind}"].parameter_count, 65536)
        self.assertEqual(rows["features.local_slot"].shape, (16, 768))
        output = StringIO()
        with redirect_stdout(output):
            print_bamf_parameter_census(spec, self.extents())
        self.assertIn("TOTAL_PARAMETERS 79469798", output.getvalue())
        for item in census.parameters:
            self.assertIn("TENSOR " + item.name + " ", output.getvalue())
        self.assertEqual(census.to_record()["total_parameters"], 79469798)

    def test_parameter_census_tracks_each_independent_table_extent(self):
        spec = ModelTopologySpecV2()
        original = bamf_parameter_census(spec, self.extents())
        for banks, pages, growth in ((2, 1, 6291456), (1, 2, 2097152), (2, 2, 8388608)):
            with self.subTest(banks=banks, pages=pages):
                grown = bamf_parameter_census(spec, self.extents(banks, pages))
                self.assertEqual(grown.total, original.total + growth)
                self.assertEqual(grown.subtotals[ParameterCategory.DENSE_MATRICES], 67239936)
                self.assertEqual(grown.subtotals[ParameterCategory.ADAPTER_MATRICES], 36864)
                self.assertEqual(grown.topology_digest, original.topology_digest)
                self.assertNotEqual(grown.extents_digest, original.extents_digest)

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

    def test_invalid_extents_and_parameter_records_fail_closed(self):
        for args in ((0, 1, "a" * 64, "b" * 64, "c" * 64),
                     (1, 5, "a" * 64, "b" * 64, "c" * 64),
                     (True, 1, "a" * 64, "b" * 64, "c" * 64),
                     (1, 1, "bad", "b" * 64, "c" * 64)):
            with self.subTest(args=args), self.assertRaises(BilqisError):
                GenerationExtents(*args)
        for shape, initializer in (((0, 3), Initializer.MATRIX), ((3, 2), Initializer.CONV_IDENTITY),
                                   ((3, 4), "unknown"), ((1, 768), Initializer.IDENTITY_BANK),
                                   ((16384, 127), Initializer.MOTIF_PAGE)):
            with self.subTest(shape=shape, initializer=initializer), self.assertRaises(BilqisError):
                ParameterSpec("fixture", shape, initializer, ParameterGroup.SLOW, True)

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
