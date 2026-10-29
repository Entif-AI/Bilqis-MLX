"""A02.3 Registry mirror and resource-budget lower-bound witnesses."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.semantics.atlas_projection import AtlasLabel
from bilqis_mlx.semantics.atlas_vocabulary import plan_vocabulary_extension
from bilqis_mlx.semantics.atlas_vocabulary_resources import (
    DEFAULT_DISK_RESERVE_BYTES, DEFAULT_EXTRA_PLANNING_BYTES,
    build_registry_mirror_delta, estimate_vocabulary_resources,
)
from bilqis_mlx.semantics.tests.test_atlas_vocabulary import _allocation_fixture


class AtlasVocabularyResourceTests(unittest.TestCase):
    def test_exact_bank_cost_and_preserved_100gib_disk_reserve(self):
        snapshot, prior = _allocation_fixture()
        with patch(
            "bilqis_mlx.semantics.atlas_vocabulary.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ):
            plan = plan_vocabulary_extension(
                prior, ("urn:concept:8192",), ModelTopologySpecV2())
        short = estimate_vocabulary_resources(
            prior, plan, observed_available_bytes=0)
        self.assertEqual(short.previous_bank_count, 1)
        self.assertEqual(short.next_bank_count, 2)
        self.assertEqual(short.added_bank_bytes, 8192 * 768 * 4 * 3)
        self.assertEqual(short.disk_reserve_bytes, 100 * 1024 ** 3)
        self.assertEqual(short.extra_planning_bytes, 30 * 1024 ** 3)
        self.assertEqual(
            short.required_available_bytes_lower_bound,
            DEFAULT_DISK_RESERVE_BYTES + DEFAULT_EXTRA_PLANNING_BYTES
            + short.complete_checkpoint_bytes_lower_bound)
        self.assertFalse(short.fits)
        enough = estimate_vocabulary_resources(
            prior, plan,
            observed_available_bytes=short.required_available_bytes_lower_bound)
        self.assertTrue(enough.fits)
        with self.assertRaises(BilqisError):
            estimate_vocabulary_resources(
                prior, plan, observed_available_bytes=10**12,
                reserve_bytes=50 * 1024 ** 3)

    def test_mirror_has_exact_active_domain_and_source_derived_lineage(self):
        snapshot, prior = _allocation_fixture()
        concept = snapshot.concepts[1]
        snapshot = replace(snapshot, concepts=(
            snapshot.concepts[0],
            replace(concept, concept=replace(
                concept.concept, labels=(AtlasLabel(
                    "pref", "SHORT LABEL NOT A DEFINITION", "en"),))),
            *snapshot.concepts[2:],
        ))
        source_nt = (
            '<urn:concept:8191> <http://www.w3.org/2004/02/skos/core#definition> "semantic role 8191"@en .\n'
            '<urn:concept:8192> <http://www.w3.org/2004/02/skos/core#definition> "semantic role 8192"@en .\n'
        ).encode("utf-8")
        with patch(
            "bilqis_mlx.semantics.atlas_vocabulary.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ), patch(
            "bilqis_mlx.semantics.atlas_vocabulary_resources.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ), patch(
            "bilqis_mlx.semantics.atlas_vocabulary_resources._verify_bundle",
            return_value=(snapshot.source_bundle_id, {"canonical.nt": source_nt}),
        ):
            plan = plan_vocabulary_extension(
                prior, ("urn:concept:8192", "urn:concept:8191"),
                ModelTopologySpecV2())
            mirror = build_registry_mirror_delta(
                prior, plan, source_bundle_path=Path("/synthetic-source"))
            again = build_registry_mirror_delta(
                prior, plan, source_bundle_path=Path("/synthetic-source"))
            self.assertEqual(mirror, again)
            self.assertEqual(mirror.digest, again.digest)
            self.assertEqual(mirror.active_indices, plan.active_indices)
            self.assertEqual(
                tuple((row.abi_index, row.bank, row.row) for row in mirror.rows),
                ((8191, 0, 8191), (8192, 1, 0)))
            self.assertTrue(all(len(row.source_record_digest) == 64
                                for row in mirror.rows))
            self.assertEqual(
                tuple(row.description for row in mirror.rows),
                ("semantic role 8191", "semantic role 8192"))
            with self.assertRaises(BilqisError):
                build_registry_mirror_delta(
                    prior, replace(plan, active_indices=(0, 8191)),
                    source_bundle_path=Path("/synthetic-source"))
        with patch(
            "bilqis_mlx.semantics.atlas_vocabulary.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ), patch(
            "bilqis_mlx.semantics.atlas_vocabulary_resources.load_pinned_atlas_snapshot",
            return_value=snapshot,
        ), patch(
            "bilqis_mlx.semantics.atlas_vocabulary_resources._verify_bundle",
            return_value=(snapshot.source_bundle_id, {"canonical.nt": b""}),
        ):
            with self.assertRaises(BilqisError):
                build_registry_mirror_delta(
                    prior, plan, source_bundle_path=Path("/synthetic-source"))


if __name__ == "__main__":
    unittest.main()
