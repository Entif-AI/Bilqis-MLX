"""Literal AtlasFeatures/v2 factor and graph witnesses."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import math
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas_features import (
    FACTOR_DIM, FACTOR_ROWS, GRAPH_DIM, FeatureSchema,
    _category_map, build_feature_manifest, plan_prospective_identity_features,
)
from bilqis_mlx.semantics.atlas_projection import (
    AbiEntry, AtlasConcept, AtlasCounts, AtlasRealization,
    CorpusCoverageRow, FrozenAtlasConcept, FrozenAtlasRelation,
    FrozenAtlasSnapshot, SourceRecordRef,
)
from bilqis_mlx.semantics.frame_schema import ConceptRef
from lib.ithkuil.src.skos.relations import SEMANTIC_PREDICATES
from lib.ithkuil.src.skos.identity import Identity


RELEASE = "a" * 64
SOURCE_BUNDLE = "b" * 64
BROADER = SEMANTIC_PREDICATES["subsumption"]
NARROWER = SEMANTIC_PREDICATES["inverse_subsumption"]
ROOT_SENSE = Identity("term", ("hasSense",)).iri
SYMBOLS = {
    "urn:concept:A": ("cogal.operator.AND", 11),
    "urn:concept:B": ("cogal.operator.OR", 12),
}
OVERFLOW_GOLDEN_HEX = {
    "urn:type:0510": (
        "2a72c33e6a305a921f3da649e5ae39aa5799016cab3d955ded8959c8b90bf525"
        "765dfe780ca174d3b67aeba534dcba80f1675fb6e45a81c252f03ad30645bc21"
        "7f4b512d65b663b2836534e8306ee1581eb580481cfc54f1faaf17fece959e1c"
        "82df4834bf623d7b0bf5f7cbedac61a2e8dfd0149442d34b1b658a434c358837"),
    "urn:type:0511": (
        "4cca325d6afe74f661522049ac6de9b00878af32aed3d33c9592d613804ce8c9"
        "27352e1d3dc965a410a6cd24364606498f63cdfe71d1b83db3738dde028a674f"
        "cf55471c7313afde0c414b76b9349d67ce6c4f3ae4558d9d1e8ba69ef4f9f163"
        "c9c5d98d267aa3a357d5d5b2618b927b7a5dac235a9e1881ea76d5d1215a2ad5"),
}


def _snapshot(
    definitions=(("urn:concept:A", ("urn:type:Entity",)),),
    relations=(),
    held=(),
    *,
    release=RELEASE,
    with_source=True,
    forms=(),
    senses=(),
    kinds=(),
):
    entries = tuple(
        AbiEntry(SYMBOLS.get(semantic_id, (semantic_id, index))[1], 0,
                 SYMBOLS.get(semantic_id, (semantic_id, index))[1],
                 semantic_id, SYMBOLS.get(semantic_id, (semantic_id, index))[0],
                 "synthetic:source",
                 True, True, "SOURCE_ADMITTED")
        for index, (semantic_id, _) in enumerate(definitions)
    )
    concepts = tuple(
        FrozenAtlasConcept(
            AtlasConcept(
                semantic_id, dict(kinds).get(semantic_id, "synthetic"), types, (), tuple(
                    AtlasRealization("form:" + str(i))
                    for i in range(dict(forms).get(semantic_id, 0))),
                (), (), tuple(
                    SourceRecordRef("synthetic", "lexicon_root_senses",
                                    "sense:" + str(i))
                    for i in range(dict(senses).get(semantic_id, 0))),
            ),
            entries[index].index, 0, entries[index].index,
            True, "ADMITTED", True, "SOURCE_ADMITTED",
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


def _features(snapshot=None, *, roles=("left", "right"),
              schemas=("frame:urn:concept:A",),
              predecessor=None):
    return build_feature_manifest(
        snapshot or _snapshot(),
        FeatureSchema(
            tuple(roles), tuple(schemas), predecessor,
            tuple((schema, "source.micro.boolean-connectives/v1")
                  for schema in sorted(set(schemas)))))


class AtlasFeatureTests(unittest.TestCase):
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

    def test_overflow_f128_exact_and_append_only_predecessor_maps(self):
        many = tuple("urn:type:%04d" % index for index in range(512))
        base = _features(
            _snapshot((("urn:concept:A", many),)),
        )
        # Saturate factor maps directly to exercise the pure overflow codec.
        # Synthetic category IDs are not source-admission witnesses.
        base = replace(
            base,
            role_map=_category_map(
                tuple("role:%04d" % index for index in range(512)), None),
            schema_map=_category_map(
                tuple("schema:%04d" % index for index in range(512)), None))
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
        self.assertEqual(
            tuple(identifier for identifier, _ in row.type_overflow),
            ("urn:type:0510", "urn:type:0511"))
        for identifier, actual in row.type_overflow:
            golden_bytes = bytes.fromhex(OVERFLOW_GOLDEN_HEX[identifier])
            self.assertEqual(len(golden_bytes), FACTOR_DIM)
            expected = tuple(
                (byte / 127.5 - 1.0) / math.sqrt(FACTOR_DIM)
                for byte in golden_bytes)
            self.assertEqual(actual, expected)
        material = hashlib.sha256(
            b"bamf.factor.v2|role|role:0511|0").digest()
        self.assertAlmostEqual(
            row.role_overflow[0],
            (material[0] / 127.5 - 1.0) / math.sqrt(128))
        successor = _features(
            replace(
                _snapshot((("urn:concept:A", ("urn:type:!new", *many)),),
                          release="b" * 64),
                prior_abi_sha256=base.atlas_bundle_id),
            predecessor=base)
        self.assertEqual(successor.predecessor_digest, base.digest)
        self.assertEqual(dict(successor.type_map)["urn:type:0000"],
                         dict(base.type_map)["urn:type:0000"])
        self.assertEqual(dict(successor.role_map)["role:0000"],
                         dict(base.role_map)["role:0000"])
        self.assertEqual(dict(successor.schema_map)["schema:0000"],
                         dict(base.schema_map)["schema:0000"])
        self.assertEqual(dict(successor.type_map)["urn:type:!new"], 0)
        self.assertEqual(dict(successor.role_map)["left"], 0)
        self.assertEqual(dict(successor.schema_map)["frame:urn:concept:A"], 0)

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
                "urn:concept:A", "role:future",
                "frame:urn:concept:A", "task:scope")
        with self.assertRaises(BilqisError):
            manifest.features_for(
                ConceptRef("urn:concept:A", "c" * 64, 0,
                           ("urn:type:Entity",), "synthetic:source"),
                "left", "frame:urn:concept:A", "task:scope")
        with self.assertRaises(BilqisError):
            _features(roles=("UNKNOWN",))
        with self.assertRaises(BilqisError):
            _features(roles=("role:INVENTED",))
        with self.assertRaises(BilqisError):
            _features(schemas=("schema:INVENTED",))
        tampered = _snapshot()
        forged_entry = replace(tampered.abi_entries[0], index=99, row=99)
        with self.assertRaises(BilqisError):
            _features(replace(tampered, abi_entries=(forged_entry,)))
        with self.assertRaises(BilqisError):
            _features(_snapshot(release=RELEASE), predecessor=manifest)
        with self.assertRaises(BilqisError):
            _features(_snapshot(release="b" * 64), predecessor=manifest)
        with self.assertRaises(BilqisError):
            manifest.features_for(
                ConceptRef("urn:concept:A", RELEASE, 99,
                           ("urn:type:Entity",), "synthetic:source"),
                "left", "frame:urn:concept:A", "task:scope")
        with self.assertRaises(BilqisError):
            manifest.features_for(
                ConceptRef("urn:concept:A", RELEASE, 11,
                           ("urn:type:Invented",), "synthetic:source"),
                "left", "frame:urn:concept:A", "task:scope")

    def test_existing_formal_source_abi_is_projected_without_oracle_or_network(self):
        from bilqis_mlx.semantics.tests.frame_adapters.helpers import _snapshot
        from unittest.mock import patch
        import socket

        snapshot = _snapshot()
        with patch.object(socket, "socket", side_effect=AssertionError("network")):
            manifest = _features(snapshot, roles=(), schemas=())
            row = manifest.features_for(
                snapshot.abi_entries[0].semantic_id,
                "NONE", "NONE", "task:scope")
        self.assertEqual(len(manifest.concepts), len(snapshot.abi_entries))
        self.assertTrue(all(
            item.source_status == "ADMITTED_FORMAL_ABI_UNTYPED"
            for item in manifest.concepts))
        self.assertEqual(row.graph64[7], 1.0)

    def test_actual_a03_micro_and_numeric_schema_authority_is_admitted(self):
        from bilqis_mlx.semantics.tests.frame_adapters.helpers import _snapshot

        snapshot = _snapshot()
        schema_ids = (
            "frame:legacy:cogal.operator.AND",
            "frame:legacy:school.op.ADD",
        )
        manifest = build_feature_manifest(
            snapshot, FeatureSchema(
                ("arg0", "arg1", "left", "right"), schema_ids,
                source_bindings=((schema_ids[0], "source.micro.boolean-connectives/v1"), (schema_ids[1], "source.finite-numeric/v2"))))
        numeric = manifest.features_for(
            "legacy:school.op.ADD", "arg0", schema_ids[1], "task:scope")
        micro = manifest.features_for(
            "legacy:cogal.operator.AND", "left", schema_ids[0], "task:scope")
        self.assertEqual(numeric.abi_index, 114)
        self.assertEqual(micro.abi_index, 11)
        self.assertNotEqual(numeric.schema_row, micro.schema_row)
        with self.assertRaises(BilqisError):
            build_feature_manifest(
                snapshot, FeatureSchema(
                    ("left", "right"), (schema_ids[1],),
                    source_bindings=((schema_ids[1], "source.finite-numeric/v2"),)))


    def test_prospective_inactive_identity_features_are_source_bound(self):
        snapshot = _snapshot(
            definitions=(("urn:concept:A", ("urn:type:Entity",)),
                         ("urn:concept:B", ("urn:type:Future",))),
            relations=(("urn:concept:B", BROADER, "urn:concept:A"),))
        inactive_entries = tuple(
            replace(entry, source="CANONICAL_SKOS", active=False, teaching_candidate=False,
                    reason="IMPLEMENTATION_UNCOVERED")
            if entry.semantic_id == "urn:concept:B" else entry
            for entry in snapshot.abi_entries)
        inactive_concepts = tuple(
            replace(item, active=False, implementation_status="IMPLEMENTATION_UNCOVERED",
                    teaching_candidate=False, teaching_reason="IMPLEMENTATION_UNCOVERED")
            if item.concept.semantic_id == "urn:concept:B" else item
            for item in snapshot.concepts)
        snapshot = replace(snapshot, abi_entries=inactive_entries, concepts=inactive_concepts)
        current = _features(snapshot, roles=(), schemas=())

        plan = plan_prospective_identity_features(
            snapshot, current, ("urn:concept:B",),
            expected_feature_digest=current.digest)

        self.assertEqual(plan.predecessor_feature_digest, current.digest)
        self.assertEqual(dict(plan.type_map)["urn:type:Entity"], 2)
        self.assertEqual(dict(plan.type_map)["urn:type:Future"], 3)
        self.assertEqual(len(plan.identities), 1)
        candidate = plan.identities[0]
        self.assertEqual(candidate.semantic_id, "urn:concept:B")
        self.assertEqual(candidate.type_ids, ("urn:type:Future",))
        self.assertEqual(candidate.type_rows, (3,))
        self.assertEqual(candidate.type_overflow, (None,))
        self.assertEqual(candidate.source_status, "SOURCE_ELIGIBLE_NOT_ADMITTED")
        self.assertGreater(candidate.graph64[1], 0.0)
        self.assertEqual(current, _features(snapshot, roles=(), schemas=()))

        with self.assertRaises(BilqisError):
            plan_prospective_identity_features(
                snapshot, current, ("urn:concept:B",),
                expected_feature_digest="0" * 64)
        with self.assertRaises(BilqisError):
            plan_prospective_identity_features(
                _snapshot(), _features(roles=(), schemas=()),
                ("urn:concept:A",),
                expected_feature_digest=_features(roles=(), schemas=()).digest)


if __name__ == "__main__":
    unittest.main()
