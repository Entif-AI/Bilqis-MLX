from __future__ import annotations
import unittest
import tempfile
from pathlib import Path
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, SKOS
from lib.ithkuil.src.skos.builder import BuildResult
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.ledger import build_ledger, ledger_json_bytes
from lib.ithkuil.src.skos.ledger_model import ExplicitDisposition
from lib.ithkuil.src.skos.preflight import CompilerClosure
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable
from lib.ithkuil.src.skos.resolver import RecordRef, Resolution, ResolvedResource
PROFILE_VERSION = 'bilqis.skos-profile/test-v1'
PROFILE_DIGEST = 'sha256:0123456789abcdef'

def _row(**fields: str) -> FrozenRow:
    return FrozenRow(tuple(sorted(fields.items())))

def _table(name: str, *rows: FrozenRow) -> LoadedTable:
    columns = tuple((key for key, _ in rows[0].values)) if rows else ()
    return LoadedTable(name, columns, tuple(rows))

def _closure(*tables: LoadedTable) -> CompilerClosure:
    return CompilerClosure('bilqis.skos.compiler-input/test-v1', tuple(tables))

def _atom(key: str) -> FrozenRow:
    return _row(atomic_id=key, category_code='CAT', value_code='VALUE', morpheme_class='vocalic_exponent', primary_source_id='official-grammar', primary_section_id='sec-1', primary_table_id='table-1', primary_source_line='42', primary_source_anchor='anchor-42', surface_form_raw='a')

def _resource(identity: Identity, ref: RecordRef, *, family: str='') -> ResolvedResource:
    families = (family,) if family else ()
    return ResolvedResource(identity, 'concept', (ref,), (), families, (), ())

def _ledger(closure: CompilerClosure, resolution: Resolution, build: BuildResult, **kwargs):
    return build_ledger(closure, resolution, build, profile_version=PROFILE_VERSION, profile_digest=PROFILE_DIGEST, **kwargs)

class HeldLedgerBoundaryTests(unittest.TestCase):

    def test_explicit_primary_disposition_cannot_claim_emission_or_hide_semantic_row(self) -> None:
        for status in ['EMITTED', 'IR_ONLY']:
            with self.subTest(status=status):
                row = _atom('m1')
                ref = RecordRef('morphemes_atomic', 'm1')
                ledger = _ledger(_closure(_table('morphemes_atomic', row)), Resolution((), ()), BuildResult(Graph(), (), ()), explicit_dispositions=(ExplicitDisposition(ref, status, 'OWNER_RESULT', 'fixture'),))
                self.assertEqual([(entry.status, entry.reason_code) for entry in ledger.entries], [('REJECTED', 'MISSING_SEMANTIC_OUTCOME')])
                self.assertEqual({item.code for item in ledger.diagnostics}, {'INVALID_PRIMARY_EXPLICIT_STATUS', 'MISSING_SEMANTIC_OUTCOME'})
                self.assertIs(ledger.blocking, True)

    def test_emitted_resource_must_equal_the_unique_canonical_resolution_object(self) -> None:
        row = _atom('m1')
        ref = RecordRef('morphemes_atomic', 'm1')
        identity = Identity('grammar', ('CAT', 'VALUE'))
        canonical = _resource(identity, ref)
        forged = _resource(identity, ref, family='wrong-family')
        graph = Graph()
        graph.add((URIRef(identity.iri), RDF.type, SKOS.Concept))
        ledger = _ledger(_closure(_table('morphemes_atomic', row)), Resolution((canonical,), ()), BuildResult(graph, (forged,), ()))
        self.assertEqual([(entry.status, entry.reason_code) for entry in ledger.entries], [('REJECTED', 'INVALID_EMITTED_RESOURCE')])
        self.assertEqual({item.code for item in ledger.diagnostics}, {'HELD_RESOURCE_IN_STRONG_GRAPH', 'INVALID_EMITTED_RESOURCE'})

    def test_unexpected_strong_semantic_subject_not_in_build_emitted_is_blocking(self) -> None:
        graph = Graph()
        extra = Identity('grammar', ('CAT', 'EXTRA'))
        graph.add((URIRef(extra.iri), RDF.type, SKOS.Concept))
        ledger = _ledger(_closure(_table('source_manifest', _row(source_id='official-grammar'))), Resolution((), ()), BuildResult(graph, (), ()))
        self.assertIn('UNACCOUNTED_STRONG_SEMANTIC_SUBJECT', {item.code for item in ledger.diagnostics})
        self.assertIs(ledger.blocking, True)

    def test_duplicate_resolution_iri_is_blocking_even_when_variants_share_iri(self) -> None:
        row = _atom('m1')
        ref = RecordRef('morphemes_atomic', 'm1')
        identity = Identity('grammar', ('CAT', 'VALUE'))
        first = _resource(identity, ref)
        second = _resource(identity, ref, family='duplicate-variant')
        ledger = _ledger(_closure(_table('morphemes_atomic', row)), Resolution((first, second), ()), BuildResult(Graph(), (), ()))
        self.assertIn('DUPLICATE_RESOLUTION_IRI', {item.code for item in ledger.diagnostics})
        self.assertIs(ledger.blocking, True)

    def test_unsafe_stable_identity_is_preserved_but_public_serialization_rejects_it(self) -> None:
        unsafe_key = '/Users/example/private-source'
        ledger = _ledger(_closure(_table('source_manifest', _row(source_id=unsafe_key))), Resolution((), ()), BuildResult(Graph(), (), ()))
        self.assertEqual(ledger.entries[0].key, unsafe_key)
        self.assertIn('UNSAFE_LEDGER_IDENTITY_FIELD', {item.code for item in ledger.diagnostics})
        with self.assertRaises(ProfileError) as error:
            ledger_json_bytes(ledger)
        self.assertEqual(error.exception.code, 'UNSAFE_LEDGER_IDENTITY_FIELD')

    def test_unsafe_explicit_semantic_key_is_not_redacted_into_public_json(self) -> None:
        row = _atom('m1')
        ref = RecordRef('morphemes_atomic', 'm1')
        disposition = ExplicitDisposition(ref, 'HELD', 'UNADMITTED_MAPPING', 'fixture', Identity('grammar', ('CAT', 'ATTEMPTED')).iri, ('file:///Users/example/private-key',))
        ledger = _ledger(_closure(_table('morphemes_atomic', row)), Resolution((), ()), BuildResult(Graph(), (), ()), explicit_dispositions=(disposition,))
        self.assertEqual(ledger.entries[0].semantic_key, ('file:///Users/example/private-key',))
        self.assertIn('UNSAFE_LEDGER_IDENTITY_FIELD', {item.code for item in ledger.diagnostics})
        with self.assertRaises(ProfileError) as error:
            ledger_json_bytes(ledger)
        self.assertEqual(error.exception.code, 'UNSAFE_LEDGER_IDENTITY_FIELD')
if __name__ == '__main__':
    unittest.main()
