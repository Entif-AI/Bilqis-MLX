"""B07.4 exact B01 motif tensor custody and prefix isolation."""
from unittest import TestCase

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_engram_parameters import (
    MotifParameterView, SITE_NAMES, motif_parameter_view,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
)


def _ledger(page_count=1):
    spec = ModelTopologySpecV2()
    extents = GenerationExtents(
        1, page_count, "a" * 64, "b" * 64, "c" * 64)
    declared = expected_bamf_shapes(spec, extents)
    return spec, extents, {
        item.name: mx.zeros(item.shape, dtype=mx.float32)
        for item in declared
    }


class MotifParameterViewTests(TestCase):
    def test_both_sites_borrow_only_exact_b01_motif_tensors(self):
        spec, extents, parameters = _ledger()
        before_keys = tuple(parameters)
        first = motif_parameter_view(
            parameters, spec=spec, extents=extents, site_index=0)
        second = motif_parameter_view(
            parameters, spec=spec, extents=extents, site_index=1)
        self.assertEqual(set(first), {"page.0", *SITE_NAMES})
        self.assertEqual(set(second), set(first))
        self.assertIs(first["page.0"], parameters["motif.page.0"])
        self.assertIs(second["page.0"], first["page.0"])
        for name in SITE_NAMES:
            self.assertIs(first[name], parameters[f"motif.site.0.{name}"])
            self.assertIs(second[name], parameters[f"motif.site.1.{name}"])
            self.assertIsNot(first[name], second[name])
        self.assertEqual(tuple(parameters), before_keys)
        self.assertNotIn("depth.query", first)
        self.assertNotIn("features.norm", first)
        self.assertNotIn("identity.bank.0", first)
        with self.assertRaises(TypeError):
            first._tensors["page.0"] = second["page.0"]
        with self.assertRaises(BilqisError):
            MotifParameterView(dict(first), 0, 1, object())

    def test_page_growth_uses_expanded_b01_ledger_without_reindexing(self):
        spec, extents, parameters = _ledger(2)
        view = motif_parameter_view(
            parameters, spec=spec, extents=extents, site_index=1)
        self.assertEqual(set(view), {"page.0", "page.1", *SITE_NAMES})
        self.assertIs(view["page.0"], parameters["motif.page.0"])
        self.assertIs(view["page.1"], parameters["motif.page.1"])
        self.assertEqual(view["page.1"].shape, (16384, 128))
        self.assertEqual(len(parameters), len(expected_bamf_shapes(spec, extents)))

    def test_full_ledger_and_site_authority_fail_closed(self):
        spec, extents, parameters = _ledger()
        for changed in (
            {"motif.site.0.projection": mx.zeros((128, 768), dtype=mx.float32)},
            {"motif.site.1.bias": mx.zeros((1,), dtype=mx.float16)},
            {"features.norm": mx.zeros((768,), dtype=mx.float16)},
            {"unexpected": mx.zeros((1,), dtype=mx.float32)},
        ):
            invalid = dict(parameters)
            invalid.update(changed)
            with self.subTest(changed=tuple(changed)), self.assertRaises(BilqisError):
                motif_parameter_view(
                    invalid, spec=spec, extents=extents, site_index=0)
        missing = dict(parameters)
        missing.pop("depth.query")
        with self.assertRaises(BilqisError):
            motif_parameter_view(
                missing, spec=spec, extents=extents, site_index=1)
        for bad in (-1, 2, True, 1.5):
            with self.assertRaises(BilqisError):
                motif_parameter_view(
                    parameters, spec=spec, extents=extents, site_index=bad)
