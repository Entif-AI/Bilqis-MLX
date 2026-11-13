"""Behavior tests split from their shared fixture owner."""
from __future__ import annotations
from dataclasses import replace
import hashlib
import math
import unittest
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas_features import FACTOR_DIM, FACTOR_ROWS, GRAPH_DIM, FeatureSchema, _category_map, build_feature_manifest, plan_prospective_identity_features
from bilqis_mlx.semantics.atlas_projection import AbiEntry, AtlasConcept, AtlasCounts, AtlasRealization, CorpusCoverageRow, FrozenAtlasConcept, FrozenAtlasRelation, FrozenAtlasSnapshot, SourceRecordRef
from bilqis_mlx.semantics.frame_schema import ConceptRef
from lib.ithkuil.src.skos.relations import SEMANTIC_PREDICATES
from lib.ithkuil.src.skos.identity import Identity
from bilqis_mlx.semantics.tests.test_atlas_features import RELEASE, SOURCE_BUNDLE, BROADER, NARROWER, ROOT_SENSE, SYMBOLS, OVERFLOW_GOLDEN_HEX, _snapshot, _features, AtlasFeatureTests

class AtlasFeatureTests1(AtlasFeatureTests):
    def test_unresolved_channel_uses_source_hold_not_implementation_debt(self):
        base = _snapshot()
        debt = CorpusCoverageRow(
            "synthetic", "source", "candidate", "urn:concept:A",
            "SOURCE_ELIGIBLE", "IMPLEMENTATION_UNCOVERED",
            False, "IMPLEMENTATION_UNCOVERED",
            "IMPLEMENTATION_UNCOVERED", "synthetic:owner")
        source_held = replace(
            debt, source_disposition="SOURCE_HELD",
            implementation_status="NOT_APPLICABLE",
            reason_code="NOTATION_COLLISION")
        debt_row = _features(replace(base, withheld_rows=(debt,))).features_for(
            "urn:concept:A", "left", "frame:urn:concept:A", "task:scope")
        held_row = _features(replace(
            base, withheld_rows=(source_held,))).features_for(
            "urn:concept:A", "left", "frame:urn:concept:A", "task:scope")
        self.assertEqual(debt_row.graph64[7], 0.0)
        self.assertEqual(held_row.graph64[7], 1.0)

    def test_disconnected_one_type_literal_graph_and_reserved_rows(self):
        manifest = _features()
        self.assertEqual(dict(manifest.type_map)["UNKNOWN"], 0)
        self.assertEqual(dict(manifest.type_map)["NONE"], 1)
        self.assertEqual(dict(manifest.type_map)["urn:type:Entity"], 2)
        row = manifest.features_for(
            "urn:concept:A", "left", "frame:urn:concept:A", "task:scope")
        self.assertEqual(row.type_rows, (2,))
        self.assertEqual(row.role_row, 2)
        self.assertEqual(row.schema_row, 2)
        self.assertEqual(len(row.graph64), GRAPH_DIM)
        self.assertAlmostEqual(
            row.graph64[4], math.log(2) / math.log(1025))
        self.assertEqual(
            tuple(value for index, value in enumerate(row.graph64) if index != 4),
            (0.0,) * (GRAPH_DIM - 1))
        self.assertEqual(row.semantic_id, "urn:concept:A")
        self.assertEqual(row.abi_index, 11)
        self.assertEqual(row.source_status, "ADMITTED_SOURCE")
        unknown = manifest.features_for(
            "urn:concept:A", "UNKNOWN", "UNKNOWN", "task:scope")
        self.assertEqual((unknown.role_row, unknown.schema_row), (0, 0))
        self.assertIsNone(unknown.role_overflow)
        self.assertIsNone(unknown.schema_overflow)
        none = manifest.features_for(
            "urn:concept:A", "NONE", "NONE", "task:scope")
        self.assertEqual((none.role_row, none.schema_row), (1, 1))
        self.assertIsNone(none.role_overflow)
        self.assertIsNone(none.schema_overflow)

    def test_graph_channels_signed_hash_and_role_swap_are_deterministic(self):
        snapshot = _snapshot(
            (("urn:concept:A", ("urn:type:Entity",)),
             ("urn:concept:B", ("urn:type:Entity",))),
            relations=(("urn:concept:A", BROADER, "urn:concept:B"),),
        )
        manifest = _features(
            snapshot, roles=("left", "right"))
        left = manifest.features_for(
            "urn:concept:A", "left", "frame:urn:concept:A", "task:scope")
        swapped = manifest.features_for(
            "urn:concept:A", "right", "frame:urn:concept:A", "task:scope")
        right = manifest.features_for(
            "urn:concept:B", "left", "frame:urn:concept:A", "task:scope")
        one = math.log(2) / math.log(1025)
        self.assertAlmostEqual(left.graph64[1], one)
        self.assertAlmostEqual(left.graph64[2], one)
        self.assertAlmostEqual(right.graph64[0], one)
        self.assertEqual(left.semantic_id, swapped.semantic_id)
        self.assertEqual(left.graph64, swapped.graph64)
        self.assertNotEqual(left.role_row, swapped.role_row)
        signature = "out|" + BROADER + "|urn:type:Entity"
        digest = hashlib.sha256(
            ("bamf.graph.v2|" + signature).encode()).digest()
        channel = 8 + (int.from_bytes(digest[:8], "little") % 56)
        sign = 1.0 if digest[8] & 1 == 0 else -1.0
        self.assertAlmostEqual(left.graph64[channel], sign)

    def test_signed_hash_collision_accumulates_opposite_signs(self):
        first = "urn:type:collision-016"
        second = "urn:type:collision-020"
        snapshot = _snapshot(
            (("urn:concept:A", ("urn:type:Entity",)),
             ("urn:concept:B", (first,)),
             ("urn:concept:C", (second,))),
            relations=(("urn:concept:A", BROADER, "urn:concept:B"),
                       ("urn:concept:A", BROADER, "urn:concept:C")))
        row = _features(snapshot).features_for(
            "urn:concept:A", "left", "frame:urn:concept:A", "task:scope")
        self.assertEqual(row.graph64[47], 0.0)
        self.assertEqual(
            hashlib.sha256(("bamf.graph.v2|out|" + BROADER + "|" + first)
                           .encode()).hexdigest(),
            "e7b8fd26bc3906642f1fa6f1153e0ec3e1672dc29b686b62bcb57e12df4718d3")
        self.assertEqual(
            hashlib.sha256(("bamf.graph.v2|out|" + BROADER + "|" + second)
                           .encode()).hexdigest(),
            "2fad1cd42f8e7e6d62c06766af742ede474d95864311c56be0b55dd8a0e2d6a7")
        self.assertEqual(row.graph64[8:], (0.0,) * 56)
        self.assertAlmostEqual(row.graph64[1], math.log(3) / math.log(1025))
        self.assertAlmostEqual(row.graph64[2], math.log(3) / math.log(1025))

    def test_held_relations_and_unadmitted_targets_do_not_leak(self):
        snapshot = _snapshot(
            (("urn:concept:A", ("urn:type:Entity",)),),
            relations=(("urn:concept:A", NARROWER, "urn:concept:HELD"),),
            held=("urn:concept:HELD",),
        )
        manifest = _features(snapshot)
        row = manifest.features_for(
            "urn:concept:A", "left", "frame:urn:concept:A", "task:scope")
        self.assertEqual(row.graph64[1], 0.0)
        self.assertEqual(row.graph64[3], 0.0)
        self.assertTrue(all(value == 0 for value in row.graph64[8:]))
        self.assertEqual(
            manifest.held_reasons,
            (("urn:concept:HELD", "SOURCE_UNRESOLVED"),))
        with self.assertRaises(BilqisError):
            manifest.features_for(
                "urn:concept:HELD", "left", "frame:urn:concept:A", "task:scope")

    def test_relational_ir_only_edge_between_admitted_nodes_is_excluded(self):
        snapshot = _snapshot(
            (("urn:concept:A", ("urn:type:Entity",)),
             ("urn:concept:B", ("urn:type:Entity",))),
            relations=(("urn:concept:A", "urn:unqualified:relational-only",
                        "urn:concept:B"),))
        row = _features(snapshot).features_for(
            "urn:concept:A", "left", "frame:urn:concept:A", "task:scope")
        self.assertEqual(row.graph64[1], 0.0)
        self.assertTrue(all(value == 0.0 for value in row.graph64[8:]))

    def test_source_form_and_attested_sense_counts(self):
        snapshot = _snapshot(
            (("urn:concept:A", ("urn:type:Entity",)),
             ("urn:sense:1", ("urn:type:Sense",)),
             ("urn:sense:2", ("urn:type:Sense",))),
            relations=(("urn:concept:A", ROOT_SENSE, "urn:sense:1"),
                       ("urn:concept:A", ROOT_SENSE, "urn:sense:2")),
            forms=(("urn:concept:A", 3),),
            senses=(("urn:sense:1", 1), ("urn:sense:2", 1)),
            kinds=(("urn:concept:A", "root"), ("urn:sense:1", "sense"),
                   ("urn:sense:2", "sense")))
        row = _features(snapshot).features_for(
            "urn:concept:A", "left", "frame:urn:concept:A", "task:scope")
        self.assertAlmostEqual(row.graph64[5], math.log(4) / math.log(1025))
        self.assertAlmostEqual(row.graph64[6], math.log(3) / math.log(1025))
        self.assertAlmostEqual(row.graph64[1], math.log(3) / math.log(1025))
        skos_linked = replace(snapshot, relations=(
            FrozenAtlasRelation("urn:concept:A", NARROWER, "urn:sense:1"),
            FrozenAtlasRelation("urn:concept:A", NARROWER, "urn:sense:2")))
        skos_row = _features(skos_linked).features_for(
            "urn:concept:A", "left", "frame:urn:concept:A", "task:scope")
        self.assertEqual(skos_row.graph64[6], row.graph64[6])

    def test_untyped_admitted_formal_abi_is_not_given_invented_types(self):
        manifest = _features(_snapshot(with_source=False))
        row = manifest.features_for(
            "urn:concept:A", "left", "frame:urn:concept:A", "task:scope")
        self.assertEqual(row.type_ids, ())
        self.assertEqual(row.type_rows, ())
        self.assertEqual(row.graph64[7], 1.0)
        self.assertEqual(row.source_status, "ADMITTED_FORMAL_ABI_UNTYPED")
