"""Fail-closed definition normalization proofs for issue #46."""
from __future__ import annotations

from pathlib import Path
import unittest

from rdflib import URIRef
from rdflib.namespace import RDF, SKOS

from lib.ithkuil.src.skos.builder import build_core_graph
from lib.ithkuil.src.skos.definition import HELD_CONFLICT, normalize_atomic_definitions
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.ledger import build_ledger
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable
from lib.ithkuil.src.skos.realization import normalize_atomic_realizations
from lib.ithkuil.src.skos.resolver import RecordRef, resolve_identities
from lib.ithkuil.src.skos.source import SourceProjector


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


class DefinitionHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.closure = preflight(SOURCE_ROOT).require_valid()

    def test_non_equivalent_summary_conflict_is_held_with_exact_rows(self) -> None:
        closure = _replace_atomic(
            self.closure,
            "ATOM-c2249e51c173ff",
            semantic_summary="different semantic claim that is not a realization qualifier",
        )
        resolution = resolve_identities(closure)
        realizations = normalize_atomic_realizations(closure, resolution)
        normalized = normalize_atomic_definitions(closure, resolution, realizations)
        issue = next(item for item in normalized.added_issues if item.code == "CONFLICTING_SEMANTIC_MEANING")
        self.assertEqual(issue.semantic_key, ("EFFECT", "1:BEN"))
        self.assertEqual(
            set(issue.record_refs),
            {
                RecordRef("morphemes_atomic", "ATOM-bab207e06f0db1"),
                RecordRef("morphemes_atomic", "ATOM-c2249e51c173ff"),
            },
        )
        self.assertIn("field=semantic_summary", issue.details)
        iri = Identity("grammar", ("EFFECT", "1:BEN")).iri
        self.assertFalse(any(resource.identity.iri == iri for resource in normalized.resolution.resources))
        candidates = [item for item in normalized.candidates if item.identity_iri == iri]
        self.assertEqual({item.classification for item in candidates}, {HELD_CONFLICT})

    def test_definition_conflict_flows_into_ledger_and_emits_no_strong_resource(self) -> None:
        closure = _replace_atomic(
            self.closure,
            "ATOM-c2249e51c173ff",
            semantic_summary="different semantic claim that is not a realization qualifier",
        )
        resolution = resolve_identities(closure)
        normalized = normalize_atomic_definitions(
            closure,
            resolution,
            normalize_atomic_realizations(closure, resolution),
        )
        built = build_core_graph(normalized.resolution.resources, SourceProjector(closure))
        ledger = build_ledger(
            closure,
            normalized.resolution,
            built,
            profile_version="bilqis-skos-profile/1",
            profile_digest="definition-fixture-profile-digest",
        )
        refs = {"ATOM-bab207e06f0db1", "ATOM-c2249e51c173ff"}
        entries = [entry for entry in ledger.entries if entry.table == "morphemes_atomic" and entry.key in refs]
        self.assertEqual(len(entries), 2)
        self.assertTrue(all(entry.status == "HELD" for entry in entries))
        self.assertTrue(all(entry.reason_code == "CONFLICTING_SEMANTIC_MEANING" for entry in entries))
        iri = URIRef(Identity("grammar", ("EFFECT", "1:BEN")).iri)
        self.assertNotIn((iri, RDF.type, SKOS.Concept), built.graph)

    def test_conflict_disposition_is_source_order_independent(self) -> None:
        closure = _replace_atomic(
            self.closure,
            "ATOM-c2249e51c173ff",
            semantic_summary="different semantic claim that is not a realization qualifier",
        )
        reversed_closure = CompilerClosure(
            closure.manifest_version,
            tuple(
                LoadedTable(table.name, table.columns, tuple(reversed(table.rows)))
                for table in reversed(closure.tables)
            ),
        )
        first_resolution = resolve_identities(closure)
        second_resolution = resolve_identities(reversed_closure)
        first = normalize_atomic_definitions(
            closure, first_resolution, normalize_atomic_realizations(closure, first_resolution)
        )
        second = normalize_atomic_definitions(
            reversed_closure,
            second_resolution,
            normalize_atomic_realizations(reversed_closure, second_resolution),
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
