"""Literal AtlasFeatures/v2 factor and graph witnesses."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import math
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas_features import (
    FACTOR_DIM, FACTOR_ROWS, GRAPH_DIM, FeatureSchema,
    build_feature_manifest,
)
from bilqis_mlx.semantics.atlas_projection import (
    AbiEntry, AtlasConcept, AtlasCounts, AtlasRealization,
    CorpusCoverageRow, FrozenAtlasConcept, FrozenAtlasRelation,
    FrozenAtlasSnapshot, SourceRecordRef,
)
from bilqis_mlx.semantics.frame_schema import ConceptRef
from lib.ithkuil.src.skos.relations import SEMANTIC_PREDICATES


RELEASE = "a" * 64
SOURCE_BUNDLE = "b" * 64
BROADER = SEMANTIC_PREDICATES["subsumption"]
NARROWER = SEMANTIC_PREDICATES["inverse_subsumption"]


def _snapshot(
    definitions=(("urn:concept:A", ("urn:type:Entity",)),),
    relations=(),
    held=(),
    *,
    release=RELEASE,
    with_source=True,
    forms=(),
    senses=(),
):
    entries = tuple(
        AbiEntry(index, 0, index, semantic_id, semantic_id, "synthetic:source",
                 True, True, "SOURCE_ADMITTED")
        for index, (semantic_id, _) in enumerate(definitions)
    )
    concepts = tuple(
        FrozenAtlasConcept(
            AtlasConcept(
                semantic_id, "synthetic", types, (), tuple(
                    AtlasRealization("form:" + str(i))
                    for i in range(dict(forms).get(semantic_id, 0))),
                (), (), tuple(
                    SourceRecordRef("synthetic", "lexicon_root_senses",
                                    "sense:" + str(i))
                    for i in range(dict(senses).get(semantic_id, 0))),
            ),
            index, 0, index, True, "ADMITTED", True, "SOURCE_ADMITTED",
        )
        for index, (semantic_id, types) in enumerate(definitions)
        if with_source
    )
    withheld = tuple(
        CorpusCoverageRow(
            "synthetic", "held", semantic_id, semantic_id,
            "HELD", "HELD", False, "SOURCE_UNRESOLVED",
            "NOT_ADMITTED", "synthetic:owner")
        for semantic_id in held
    )
    return FrozenAtlasSnapshot(
        "bilqis.semantic-atlas-snapshot/v1", "c" * 64, release,
        SOURCE_BUNDLE, "d" * 64, "e" * 64, "f" * 64,
        "0" * 64, "1" * 64, "2" * 64, "3" * 64,
        AtlasCounts(len(entries), len(entries), len(concepts), len(entries),
                    1, len(entries), 0, len(held), 0, 0),
        (), entries, concepts, tuple(
            FrozenAtlasRelation(*edge) for edge in relations),
        withheld, tuple(sorted(
            (entry.semantic_id, entry.index) for entry in entries)),
        tuple(sorted(
            (item.concept.semantic_id, item.abi_index) for item in concepts)),
    )


def _features(snapshot=None, *, roles=("role:subject",), schemas=("schema:atom",),
              predecessor=None):
    return build_feature_manifest(
        snapshot or _snapshot(),
        FeatureSchema(tuple(roles), tuple(schemas), predecessor))


class AtlasFeatureTests(unittest.TestCase):
    def test_disconnected_one_type_literal_graph_and_reserved_rows(self):
        manifest = _features()
        self.assertEqual(dict(manifest.type_map)["UNKNOWN"], 0)
        self.assertEqual(dict(manifest.type_map)["NONE"], 1)
        self.assertEqual(dict(manifest.type_map)["urn:type:Entity"], 2)
        row = manifest.features_for(
            "urn:concept:A", "role:subject", "schema:atom", "task:scope")
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
        self.assertEqual(row.abi_index, 0)
        self.assertEqual(row.source_status, "ADMITTED_SOURCE")

    def test_graph_channels_signed_hash_and_role_swap_are_deterministic(self):
        snapshot = _snapshot(
            (("urn:concept:A", ("urn:type:Entity",)),
             ("urn:concept:B", ("urn:type:Entity",))),
            relations=(("urn:concept:A", BROADER, "urn:concept:B"),),
        )
        manifest = _features(
            snapshot, roles=("role:object", "role:subject"))
        left = manifest.features_for(
            "urn:concept:A", "role:subject", "schema:atom", "task:scope")
        swapped = manifest.features_for(
            "urn:concept:A", "role:object", "schema:atom", "task:scope")
        right = manifest.features_for(
            "urn:concept:B", "role:subject", "schema:atom", "task:scope")
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

    def test_held_relations_and_unadmitted_targets_do_not_leak(self):
        snapshot = _snapshot(
            (("urn:concept:A", ("urn:type:Entity",)),),
            relations=(("urn:concept:A", NARROWER, "urn:concept:HELD"),),
            held=("urn:concept:HELD",),
        )
        manifest = _features(snapshot)
        row = manifest.features_for(
            "urn:concept:A", "role:subject", "schema:atom", "task:scope")
        self.assertEqual(row.graph64[1], 0.0)
        self.assertEqual(row.graph64[3], 0.0)
        self.assertTrue(all(value == 0 for value in row.graph64[8:]))
        self.assertEqual(
            manifest.held_reasons,
            (("urn:concept:HELD", "SOURCE_UNRESOLVED"),))
        with self.assertRaises(BilqisError):
            manifest.features_for(
                "urn:concept:HELD", "role:subject", "schema:atom", "task:scope")

    def test_relational_ir_only_edge_between_admitted_nodes_is_excluded(self):
        snapshot = _snapshot(
            (("urn:concept:A", ("urn:type:Entity",)),
             ("urn:concept:B", ("urn:type:Entity",))),
            relations=(("urn:concept:A", "urn:unqualified:relational-only",
                        "urn:concept:B"),))
        row = _features(snapshot).features_for(
            "urn:concept:A", "role:subject", "schema:atom", "task:scope")
        self.assertEqual(row.graph64[1], 0.0)
        self.assertTrue(all(value == 0.0 for value in row.graph64[8:]))

    def test_source_form_and_attested_sense_counts(self):
        snapshot = _snapshot(
            forms=(("urn:concept:A", 3),),
            senses=(("urn:concept:A", 2),))
        row = _features(snapshot).features_for(
            "urn:concept:A", "role:subject", "schema:atom", "task:scope")
        self.assertAlmostEqual(row.graph64[5], math.log(4) / math.log(1025))
        self.assertAlmostEqual(row.graph64[6], math.log(3) / math.log(1025))

    def test_untyped_admitted_formal_abi_is_not_given_invented_types(self):
        manifest = _features(_snapshot(with_source=False))
        row = manifest.features_for(
            "urn:concept:A", "role:subject", "schema:atom", "task:scope")
        self.assertEqual(row.type_ids, ())
        self.assertEqual(row.type_rows, ())
        self.assertEqual(row.graph64[7], 1.0)
        self.assertEqual(row.source_status, "ADMITTED_FORMAL_ABI_UNTYPED")

    def test_overflow_f128_exact_and_append_only_predecessor_maps(self):
        many = tuple("urn:type:%04d" % index for index in range(512))
        base = _features(
            _snapshot((("urn:concept:A", many),)),
            roles=tuple("role:%04d" % index for index in range(512)),
            schemas=tuple("schema:%04d" % index for index in range(512)),
        )
        self.assertEqual(len(base.type_map), 514)
        self.assertEqual(
            sum(row >= 2 for _, row in base.type_map), FACTOR_ROWS - 2)
        row = base.features_for(
            "urn:concept:A", "role:0511", "schema:0511", "task:scope")
        self.assertEqual(row.role_row, 0)
        self.assertEqual(row.schema_row, 0)
        self.assertEqual(len(row.role_overflow), FACTOR_DIM)
        self.assertEqual(len(row.schema_overflow), FACTOR_DIM)
        self.assertEqual(len(row.type_overflow), 2)
        material = hashlib.sha256(
            b"bamf.factor.v2|role|role:0511|0").digest()
        self.assertAlmostEqual(
            row.role_overflow[0],
            (material[0] / 127.5 - 1.0) / math.sqrt(128))
        successor = _features(
            _snapshot((("urn:concept:A", ("urn:type:!new", *many)),),
                      release="b" * 64),
            roles=("role:!new",), schemas=("schema:!new",),
            predecessor=base)
        self.assertEqual(successor.predecessor_digest, base.digest)
        self.assertEqual(dict(successor.type_map)["urn:type:0000"],
                         dict(base.type_map)["urn:type:0000"])
        self.assertEqual(dict(successor.role_map)["role:0000"],
                         dict(base.role_map)["role:0000"])
        self.assertEqual(dict(successor.schema_map)["schema:0000"],
                         dict(base.schema_map)["schema:0000"])
        self.assertEqual(dict(successor.type_map)["urn:type:!new"], 0)
        self.assertEqual(dict(successor.role_map)["role:!new"], 0)
        self.assertEqual(dict(successor.schema_map)["schema:!new"], 0)

    def test_reordered_source_rows_do_not_change_manifest(self):
        definitions = (
            ("urn:concept:B", ("urn:type:B",)),
            ("urn:concept:A", ("urn:type:A",)),
        )
        snapshot = _snapshot(
            definitions, relations=(
                ("urn:concept:B", BROADER, "urn:concept:A"),
                ("urn:concept:A", NARROWER, "urn:concept:B"),
            ))
        reordered = replace(
            snapshot, abi_entries=tuple(reversed(snapshot.abi_entries)),
            concepts=tuple(reversed(snapshot.concepts)),
            relations=tuple(reversed(snapshot.relations)))
        self.assertEqual(_features(snapshot).digest, _features(reordered).digest)

    def test_unadmitted_role_schema_and_foreign_release_fail_closed(self):
        manifest = _features()
        with self.assertRaises(BilqisError):
            manifest.features_for(
                "urn:concept:A", "role:future", "schema:atom", "task:scope")
        with self.assertRaises(BilqisError):
            manifest.features_for(
                ConceptRef("urn:concept:A", "c" * 64, 0,
                           ("urn:type:Entity",), "synthetic:source"),
                "role:subject", "schema:atom", "task:scope")
        with self.assertRaises(BilqisError):
            _features(roles=("UNKNOWN",))
        with self.assertRaises(BilqisError):
            _features(_snapshot(release=RELEASE), predecessor=manifest)
        with self.assertRaises(BilqisError):
            manifest.features_for(
                ConceptRef("urn:concept:A", RELEASE, 99,
                           ("urn:type:Entity",), "synthetic:source"),
                "role:subject", "schema:atom", "task:scope")
        with self.assertRaises(BilqisError):
            manifest.features_for(
                ConceptRef("urn:concept:A", RELEASE, 0,
                           ("urn:type:Invented",), "synthetic:source"),
                "role:subject", "schema:atom", "task:scope")

    def test_existing_formal_source_abi_is_projected_without_oracle_or_network(self):
        from bilqis_mlx.semantics.tests.test_frame_adapters import _snapshot
        from unittest.mock import patch
        import socket

        snapshot = _snapshot()
        with patch.object(socket, "socket", side_effect=AssertionError("network")):
            manifest = _features(snapshot)
        self.assertEqual(len(manifest.concepts), len(snapshot.abi_entries))
        self.assertTrue(all(
            item.source_status == "ADMITTED_FORMAL_ABI_UNTYPED"
            for item in manifest.concepts))
        self.assertEqual(
            manifest.features_for(
                snapshot.abi_entries[0].semantic_id,
                "role:subject", "schema:atom", "task:scope").graph64[7],
            1.0)


if __name__ == "__main__":
    unittest.main()
