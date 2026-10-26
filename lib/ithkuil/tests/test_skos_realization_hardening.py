"""Fail-closed realization normalization proofs for issue #45."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable
from lib.ithkuil.src.skos.realization import normalize_atomic_realizations
from lib.ithkuil.src.skos.resolver import Resolution, resolve_identities


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "_data" / "csv"


def _mutate(row: FrozenRow, **changes: str) -> FrozenRow:
    values = dict(row.values)
    values.update(changes)
    return FrozenRow(tuple((field, values[field]) for field, _ in row.values))


def _replace_atomic(closure: CompilerClosure, atomic_id: str, **changes: str) -> CompilerClosure:
    tables = []
    for table in closure.tables:
        if table.name != "morphemes_atomic":
            tables.append(table)
            continue
        rows = tuple(
            _mutate(row, **changes) if row["atomic_id"] == atomic_id else row
            for row in table.rows
        )
        tables.append(LoadedTable(table.name, table.columns, rows))
    return CompilerClosure(closure.manifest_version, tuple(tables))


class RealizationHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.closure = preflight(SOURCE_ROOT).require_valid()
        cls.resolution = resolve_identities(cls.closure)

    def test_unknown_realization_type_has_stable_held_reason(self) -> None:
        atomic_id = "ATOM-02a4496bfbac3a"
        closure = _replace_atomic(self.closure, atomic_id, realization_type="future_contextual")
        result = normalize_atomic_realizations(closure, resolve_identities(closure))
        issue = next(item for item in result.issues if item.code == "UNKNOWN_REALIZATION_TYPE")
        self.assertEqual(issue.semantic_key, ("CONFIGURATION", "DDS"))
        self.assertEqual([(ref.table, ref.key) for ref in issue.record_refs], [("morphemes_atomic", atomic_id)])
        self.assertFalse(any(group.identity == Identity("grammar", ("CONFIGURATION", "DDS")) for group in result.groups))

    def test_blank_realization_form_is_not_equivalent_to_literal_zero(self) -> None:
        atomic_id = "ATOM-e09a479fdaca6d"
        closure = _replace_atomic(
            self.closure,
            atomic_id,
            surface_form_raw="",
            surface_form_normalized="",
        )
        result = normalize_atomic_realizations(closure, resolve_identities(closure))
        issue = next(item for item in result.issues if item.code == "MISSING_REALIZATION_FORM")
        self.assertEqual(issue.semantic_key, ("CONFIGURATION", "UPX"))
        self.assertFalse(any(group.identity == Identity("grammar", ("CONFIGURATION", "UPX")) for group in result.groups))
        baseline = normalize_atomic_realizations(self.closure, self.resolution)
        group = next(group for group in baseline.groups if group.identity == Identity("grammar", ("CONFIGURATION", "UPX")))
        self.assertEqual([item.raw_form for item in group.realizations], ["∅"])

    def test_generic_zero_plus_overt_rows_for_one_key_normalize_to_one_identity(self) -> None:
        table = self.closure.table("morphemes_atomic")
        source = next(row for row in table.rows if row["atomic_id"] == "ATOM-e09a479fdaca6d")
        overt = _mutate(
            source,
            atomic_id="ATOM-fixture-upx-overt",
            surface_form_raw="fixture-overt",
            surface_form_normalized="fixture-overt",
            realization_type="overt",
            allomorph_group_id="AG-fixture-upx-overt",
            allomorph_condition="synthetic conformance realization",
        )
        tables = tuple(
            LoadedTable(item.name, item.columns, item.rows + (overt,))
            if item.name == "morphemes_atomic" else item
            for item in self.closure.tables
        )
        closure = CompilerClosure(self.closure.manifest_version, tables)
        result = normalize_atomic_realizations(closure, resolve_identities(closure))
        identity = Identity("grammar", ("CONFIGURATION", "UPX"))
        group = next(group for group in result.groups if group.identity == identity)
        self.assertEqual(
            {(item.raw_form, item.realization_type) for item in group.realizations},
            {("∅", "zero"), ("fixture-overt", "overt")},
        )
        self.assertEqual(group.identity, identity)

    def test_changed_raw_form_and_english_label_do_not_remint_semantic_identity(self) -> None:
        atomic_id = "ATOM-02a4496bfbac3a"
        closure = _replace_atomic(
            self.closure,
            atomic_id,
            surface_form_raw="ţš",
            surface_form_normalized="ţš",
            value_name="changed display label",
        )
        resolution = resolve_identities(closure)
        result = normalize_atomic_realizations(closure, resolution)
        identity = Identity("grammar", ("CONFIGURATION", "DDS"))
        group = next(group for group in result.groups if group.identity == identity)
        self.assertEqual(group.identity.iri, identity.iri)
        self.assertEqual([(item.raw_form, item.normalized_form) for item in group.realizations], [("ţš", "ţš")])

    def test_duplicate_source_ref_is_rejected_not_deduplicated(self) -> None:
        table = self.closure.table("morphemes_atomic")
        source = next(row for row in table.rows if row["atomic_id"] == "ATOM-02a4496bfbac3a")
        tables = tuple(
            LoadedTable(item.name, item.columns, item.rows + (source,))
            if item.name == "morphemes_atomic" else item
            for item in self.closure.tables
        )
        closure = CompilerClosure(self.closure.manifest_version, tables)
        result = normalize_atomic_realizations(closure, self.resolution)
        self.assertIn("DUPLICATE_REALIZATION_SOURCE_REF", {item.code for item in result.issues})
        self.assertFalse(any(group.identity == Identity("grammar", ("CONFIGURATION", "DDS")) for group in result.groups))

    def test_allomorph_group_cannot_claim_two_distinct_semantic_keys(self) -> None:
        upx = next(
            row for row in self.closure.table("morphemes_atomic").rows
            if row["atomic_id"] == "ATOM-e09a479fdaca6d"
        )
        closure = _replace_atomic(
            self.closure,
            "ATOM-02a4496bfbac3a",
            allomorph_group_id=upx["allomorph_group_id"],
        )
        result = normalize_atomic_realizations(closure, resolve_identities(closure))
        conflict = next(item for item in result.issues if item.code == "ALLOMORPH_GROUP_SEMANTIC_CONFLICT")
        self.assertEqual(
            {(ref.table, ref.key) for ref in conflict.record_refs},
            {
                ("morphemes_atomic", "ATOM-e09a479fdaca6d"),
                ("morphemes_atomic", "ATOM-02a4496bfbac3a"),
            },
        )
        blocked = {Identity("grammar", ("CONFIGURATION", "UPX")), Identity("grammar", ("CONFIGURATION", "DDS"))}
        self.assertTrue(blocked.isdisjoint({group.identity for group in result.groups}))

    def test_incompatible_resolved_semantic_key_is_not_silently_rebound(self) -> None:
        target = next(
            resource
            for resource in self.resolution.resources
            if resource.identity == Identity("grammar", ("CONFIGURATION", "DDS"))
        )
        forged = replace(target, identity=Identity("grammar", ("CONFIGURATION", "UPX")))
        resolution = Resolution(
            tuple(forged if item == target else item for item in self.resolution.resources),
            self.resolution.issues,
        )
        result = normalize_atomic_realizations(self.closure, resolution)
        issue = next(
            item
            for item in result.issues
            if item.code == "INCOMPATIBLE_REALIZATION_SEMANTIC_KEY"
            and item.semantic_key == ("CONFIGURATION", "DDS")
        )
        self.assertEqual(issue.record_refs[0].key, "ATOM-02a4496bfbac3a")

    def test_cross_scheme_variant_is_cardinality_conflict_not_identity_merge(self) -> None:
        target = next(
            resource
            for resource in self.resolution.resources
            if resource.identity == Identity("grammar", ("CONFIGURATION", "DDS"))
        )
        variant = replace(target, schemes=(Identity("scheme", ("fixture-other",)),))
        resolution = Resolution(self.resolution.resources + (variant,), self.resolution.issues)
        result = normalize_atomic_realizations(self.closure, resolution)
        issue = next(
            item
            for item in result.issues
            if item.code == "REALIZATION_RESOURCE_CARDINALITY"
            and item.semantic_key == ("CONFIGURATION", "DDS")
        )
        self.assertEqual(issue.details, ("count=2",))
        self.assertFalse(any(group.identity == target.identity for group in result.groups))


if __name__ == "__main__":
    unittest.main()
