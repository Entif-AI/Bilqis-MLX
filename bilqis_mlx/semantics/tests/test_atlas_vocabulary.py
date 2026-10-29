"""A02 prospective identity-factor staging without B02 authority."""
from __future__ import annotations

from dataclasses import replace
import unittest

import mlx.core as mx
import numpy as np

from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes, initialize_bamf_row,
)
from bilqis_mlx.semantics.atlas_vocabulary import prepare_identity_factors
from bilqis_mlx.semantics.tests.test_atlas_features import (
    BROADER, _features, _snapshot,
)


class AtlasVocabularyTests(unittest.TestCase):
    def test_a02_stages_inactive_row_factor_without_b02_dependency(self):
        snapshot = _snapshot(
            definitions=(("urn:concept:A", ("urn:type:Entity",)),
                         ("urn:concept:B", ("urn:type:Future",))),
            relations=(("urn:concept:B", BROADER, "urn:concept:A"),))
        snapshot = replace(
            snapshot,
            abi_entries=tuple(
                replace(entry, source="CANONICAL_SKOS", active=False,
                        teaching_candidate=False, reason="IMPLEMENTATION_UNCOVERED")
                if entry.semantic_id == "urn:concept:B" else entry
                for entry in snapshot.abi_entries),
            concepts=tuple(
                replace(item, active=False,
                        implementation_status="IMPLEMENTATION_UNCOVERED",
                        teaching_candidate=False,
                        teaching_reason="IMPLEMENTATION_UNCOVERED")
                if item.concept.semantic_id == "urn:concept:B" else item
                for item in snapshot.concepts),
        )
        current = _features(snapshot, roles=(), schemas=())
        type_table = mx.zeros((512, 128), dtype=mx.float32)
        type_table = type_table.at[3].add(mx.ones((128,), dtype=mx.float32))
        parameters = {
            "features.type": type_table,
            "features.project_type": mx.ones((768, 128), dtype=mx.float32) / 128.0,
            "features.project_graph": mx.zeros((768, 64), dtype=mx.float32),
            "features.gates": mx.zeros((4,), dtype=mx.float32),
        }

        plan, factors = prepare_identity_factors(
            snapshot, current, ("urn:concept:B",), parameters,
            extents=GenerationExtents(1, 1, "a" * 64, "b" * 64, current.digest))

        self.assertEqual(tuple(name for name, _ in factors), ("urn:concept:B",))
        factor = factors[0][1]
        np.testing.assert_allclose(factor, np.full((768,), 0.5, dtype=np.float32))
        entry = next(item for item in snapshot.abi_entries
                     if item.semantic_id == "urn:concept:B")
        identity_spec = next(
            item for item in expected_bamf_shapes(
                ModelTopologySpecV2(),
                GenerationExtents(
                    1, 1, "a" * 64, "b" * 64, current.digest))
            if item.name == "identity.bank.0")
        row = initialize_bamf_row(
            identity_spec, run_seed=7, row_id=entry.semantic_id, factor=factor)
        self.assertEqual(row.shape, (768,))
        self.assertEqual(row.dtype, np.float32)
        self.assertEqual(plan.identities[0].abi_index, entry.index)
        self.assertFalse(entry.active)


if __name__ == "__main__":
    unittest.main()
