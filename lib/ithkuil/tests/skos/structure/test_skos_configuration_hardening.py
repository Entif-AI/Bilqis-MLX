"""Fail-closed Configuration projection proofs for issue #44."""
from __future__ import annotations
from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT

from dataclasses import replace
import json
from pathlib import Path
import unittest

from rdflib import URIRef
from rdflib.namespace import RDF, SKOS

from lib.ithkuil.src.skos.builder import build_core_graph
from lib.ithkuil.src.skos.configuration import select_configuration_resources
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable
from lib.ithkuil.src.skos.resolver import RecordRef, TextAssertion, resolve_identities
from lib.ithkuil.src.skos.source import SourceProjector


ROOT = ITHKUIL_ROOT
SOURCE_ROOT = ROOT / "_data" / "csv"
FIXTURES = FIXTURES


def _replace_row(row: FrozenRow, **updates: str) -> FrozenRow:
    values = dict(row.values)
    values.update(updates)
    return FrozenRow(tuple((field, values[field]) for field, _ in row.values))


def _mutate_atomic(
    closure: CompilerClosure, predicate, transform
) -> CompilerClosure:
    tables = []
    for table in closure.tables:
        if table.name != "morphemes_atomic":
            tables.append(table)
            continue
        rows = tuple(transform(row) if predicate(row) else row for row in table.rows)
        tables.append(LoadedTable(table.name, table.columns, rows))
    return CompilerClosure(closure.manifest_version, tuple(tables))


class ConfigurationHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.closure = preflight(SOURCE_ROOT).require_valid()

    def test_duplicate_source_record_is_not_silently_deduplicated(self) -> None:
        resolution = resolve_identities(self.closure)
        tables = []
        for table in self.closure.tables:
            if table.name == "morphemes_atomic":
                config = next(row for row in table.rows if row.get("category_code") == "CONFIGURATION")
                tables.append(LoadedTable(table.name, table.columns, table.rows + (config,)))
            else:
                tables.append(table)
        closure = CompilerClosure(self.closure.manifest_version, tuple(tables))
        with self.assertRaises(ProfileError) as error:
            select_configuration_resources(closure, resolution)
        self.assertEqual(error.exception.code, "CONFIGURATION_DUPLICATE_SOURCE_RECORD")

    def test_conflicting_definition_for_one_configuration_identity_is_held(self) -> None:
        fixture = json.loads((FIXTURES / "configuration_malformed.json").read_text(encoding="utf-8"))
        table = self.closure.table("morphemes_atomic")
        mss = next(row for row in table.rows if row.get("atomic_id") == fixture["base_atomic_id"])
        extra = _replace_row(
            mss,
            atomic_id=fixture["synthetic_atomic_id"],
            **fixture["mutations"],
        )
        tables = tuple(
            LoadedTable(item.name, item.columns, item.rows + (extra,)) if item.name == "morphemes_atomic" else item
            for item in self.closure.tables
        )
        closure = CompilerClosure(self.closure.manifest_version, tables)
        resolution = resolve_identities(closure)
        issue = next(
            issue
            for issue in resolution.issues
            if issue.code == fixture["expected_resolution_issue"]
        )
        self.assertEqual(
            set(issue.record_refs),
            {
                RecordRef("morphemes_atomic", mss["atomic_id"]),
                RecordRef("morphemes_atomic", fixture["synthetic_atomic_id"]),
            },
        )
        with self.assertRaises(ProfileError) as error:
            select_configuration_resources(closure, resolution)
        self.assertEqual(error.exception.code, fixture["expected_selector_error"])

    def test_configuration_row_with_missing_value_cannot_disappear_from_selection(self) -> None:
        closure = _mutate_atomic(
            self.closure,
            lambda row: row.get("category_code") == "CONFIGURATION" and row.get("value_code") == "MSS",
            lambda row: _replace_row(row, value_code=""),
        )
        resolution = resolve_identities(closure)
        self.assertIn("MISSING_SEMANTIC_KEY", {issue.code for issue in resolution.issues})
        with self.assertRaises(ProfileError) as error:
            select_configuration_resources(closure, resolution)
        self.assertEqual(error.exception.code, "CONFIGURATION_RESOLUTION_HELD")

    def test_nonunique_form_across_distinct_values_is_held_not_merged(self) -> None:
        closure = _mutate_atomic(
            self.closure,
            lambda row: row.get("category_code") == "CONFIGURATION" and row.get("value_code") == "MSS",
            lambda row: _replace_row(row, surface_form_raw="p", surface_form_normalized="p"),
        )
        resolution = resolve_identities(closure)
        selection = select_configuration_resources(closure, resolution)
        build = build_core_graph(selection.resources, SourceProjector(closure))
        collided = {
            issue.resource_iri
            for issue in build.issues
            if issue.code == "NOTATION_COLLISION"
        }
        expected = {
            Identity("grammar", ("CONFIGURATION", "MSS")).iri,
            Identity("grammar", ("CONFIGURATION", "MSF")).iri,
        }
        self.assertEqual(collided, expected)
        self.assertEqual(len(build.emitted), 18)
        for iri in expected:
            self.assertNotIn((URIRef(iri), RDF.type, SKOS.Concept), build.graph)

    def test_conflicting_source_preferred_label_holds_the_resource(self) -> None:
        resolution = resolve_identities(self.closure)
        selection = select_configuration_resources(self.closure, resolution)
        target = next(
            resource
            for resource in selection.resources
            if resource.identity == Identity("grammar", ("CONFIGURATION", "MSS"))
        )
        ref = target.source_records[0]
        conflict = TextAssertion(
            ref,
            "value_name",
            "not the source preferred label",
            "source_pref_label",
            "resource",
            "en",
        )
        altered = replace(target, texts=target.texts + (conflict,))
        resources = tuple(altered if item == target else item for item in selection.resources)
        build = build_core_graph(resources, SourceProjector(self.closure))
        issue = next(item for item in build.issues if item.resource_iri == target.identity.iri)
        self.assertEqual(issue.code, "PREFERRED_LABEL_CONFLICT")
        self.assertNotIn((URIRef(target.identity.iri), RDF.type, SKOS.Concept), build.graph)

    def test_source_url_substitution_holds_instead_of_losing_provenance(self) -> None:
        closure = _mutate_atomic(
            self.closure,
            lambda row: row.get("category_code") == "CONFIGURATION" and row.get("value_code") == "UPX",
            lambda row: _replace_row(row, primary_source_url="https://www.ithkuil.net/newithkuil_04_case.htm"),
        )
        resolution = resolve_identities(closure)
        selection = select_configuration_resources(closure, resolution)
        build = build_core_graph(selection.resources, SourceProjector(closure))
        upx = Identity("grammar", ("CONFIGURATION", "UPX")).iri
        issue_codes = {
            issue.code
            for issue in build.issues
            if issue.resource_iri == upx
        }
        self.assertIn("SOURCE_URL_REGISTRY_MISMATCH", issue_codes)
        self.assertNotIn((URIRef(upx), RDF.type, SKOS.Concept), build.graph)
        self.assertEqual(len(build.emitted), 19)


if __name__ == "__main__":
    unittest.main()
