"""BAMF architecture identity and historical isolation."""
from __future__ import annotations

import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2, ParameterCategory, expected_bamf_shapes
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ParameterGroup, ParameterSpec, Initializer


class ParametersTests(unittest.TestCase):
    @staticmethod
    def extents(banks=1, pages=1):
        return GenerationExtents(banks, pages, "a" * 64, "b" * 64, "c" * 64)

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


    def test_adapter_matrix_categories_preserve_wire_names_and_auxiliaries(self):
        declared = expected_bamf_shapes(ModelTopologySpecV2(), self.extents())
        adapters = {p.name: p for p in declared if p.name.startswith("plastic.group.")}
        self.assertEqual(tuple(adapters), tuple(
            f"plastic.group.{group}.{suffix}"
            for group in range(3) for suffix in ("norm", "A", "B")))
        for group in range(3):
            for suffix in ("A", "B"):
                self.assertIs(adapters[f"plastic.group.{group}.{suffix}"].category,
                              ParameterCategory.ADAPTER_MATRICES)
            self.assertIs(adapters[f"plastic.group.{group}.norm"].category,
                          ParameterCategory.AUXILIARY)
