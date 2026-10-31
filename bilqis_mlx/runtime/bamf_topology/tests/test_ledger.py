"""BAMF architecture identity and historical isolation."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import math
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2, GenerationExtents, ParameterCategory, ParameterCensus, bamf_parameter_census, print_bamf_parameter_census, expected_bamf_shapes


class LedgerTests(unittest.TestCase):
    @staticmethod
    def extents(banks=1, pages=1):
        return GenerationExtents(banks, pages, "a" * 64, "b" * 64, "c" * 64)

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

    def test_parameter_census_rejects_invalid_identity_and_duplicate_rows(self):
        spec, extents = ModelTopologySpecV2(), self.extents()
        row = expected_bamf_shapes(spec, extents)[0]
        for bad_spec, bad_extents in ((None, extents), (spec, None)):
            with self.assertRaises(BilqisError):
                bamf_parameter_census(bad_spec, bad_extents)
        for topology_digest, parameters in (("bad", (row,)), (spec.digest, (row, row))):
            with self.assertRaises(BilqisError):
                ParameterCensus(topology_digest, extents.digest, parameters)
