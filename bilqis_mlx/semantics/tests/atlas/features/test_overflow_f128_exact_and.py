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

class AtlasFeatureTests2(AtlasFeatureTests):
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
