from __future__ import annotations
from lib.ithkuil.tests.source_expectations import CORE

import unittest
import tempfile
from pathlib import Path
from rdflib import Graph, URIRef
from rdflib.namespace import RDF, SKOS
from lib.ithkuil.src.skos.builder import BuildIssue, BuildResult, build_core_graph
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.ledger import build_ledger, ledger_json_bytes
from lib.ithkuil.src.skos.ledger_model import ExplicitDisposition
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable
from lib.ithkuil.src.skos.resolver import RecordRef, Resolution, ResolutionIssue, ResolvedResource, resolve_identities
from lib.ithkuil.src.skos.source import SourceProjector
PROFILE_VERSION = 'bilqis.skos-profile/test-v1'
PROFILE_DIGEST = 'sha256:0123456789abcdef'
FIXTURES = Path(__file__).with_name('fixtures')

def _row(**fields: str) -> FrozenRow:
    return FrozenRow(tuple(sorted(fields.items())))

def _table(name: str, *rows: FrozenRow) -> LoadedTable:
    columns = tuple((key for key, _ in rows[0].values)) if rows else ()
    return LoadedTable(name, columns, tuple(rows))

def _closure(*tables: LoadedTable) -> CompilerClosure:
    return CompilerClosure('bilqis.skos.compiler-input/test-v1', tuple(tables))

def _atom(key: str, *, notation: str='a', value: str='VALUE') -> FrozenRow:
    return _row(atomic_id=key, category_code='CAT', value_code=value, morpheme_class='vocalic_exponent', primary_source_id='official-grammar', primary_section_id='sec-1', primary_table_id='table-1', primary_source_line='42', primary_source_anchor='anchor-42', surface_form_raw=notation)

def _resource(identity: Identity, *refs: RecordRef) -> ResolvedResource:
    return ResolvedResource(identity, 'concept', tuple(refs), (), (), (), ())

def _emitted(resource: ResolvedResource) -> BuildResult:
    graph = Graph()
    graph.add((URIRef(resource.identity.iri), RDF.type, SKOS.Concept))
    return BuildResult(graph, (resource,), ())

def _ledger(closure: CompilerClosure, resolution: Resolution, build: BuildResult, **kwargs):
    return build_ledger(closure, resolution, build, profile_version=PROFILE_VERSION, profile_digest=PROFILE_DIGEST, **kwargs)

class HeldLedgerContractTests(unittest.TestCase):

    def test_many_source_rows_for_one_emitted_resource_are_all_emitted(self) -> None:
        rows = (_atom('m1', notation='a'), _atom('m2', notation='ä'))
        refs = (RecordRef('morphemes_atomic', 'm1'), RecordRef('morphemes_atomic', 'm2'))
        resource = _resource(Identity('grammar', ('CAT', 'VALUE')), *refs)
        ledger = _ledger(_closure(_table('morphemes_atomic', *rows)), Resolution((resource,), ()), _emitted(resource))
        self.assertEqual([(entry.key, entry.status) for entry in ledger.entries], [('m1', 'EMITTED'), ('m2', 'EMITTED')])
        self.assertEqual(ledger.counts, {'EMITTED': 2, 'HELD': 0, 'REJECTED': 0, 'UNSUPPORTED': 0, 'IR_ONLY': 0})
        self.assertIs(ledger.blocking, False)
        self.assertIs(ledger.core_complete, True)
        self.assertIs(ledger.whole_release_eligible, True)
        self.assertIs(ledger.release_ineligible, False)

    def test_held_resource_accounts_all_rows_once_and_keeps_all_reasons(self) -> None:
        rows = (_atom('m1'), _atom('m2'))
        refs = (RecordRef('morphemes_atomic', 'm1'), RecordRef('morphemes_atomic', 'm2'))
        resource = _resource(Identity('grammar', ('CAT', 'VALUE')), *refs)
        issues = (BuildIssue('NOTATION_COLLISION', resource.identity.iri, refs, ('same notation',)), BuildIssue('SOURCE_TEXT_TOO_LONG', resource.identity.iri, refs, ('field=value_name',)))
        ledger = _ledger(_closure(_table('morphemes_atomic', *rows)), Resolution((resource,), ()), BuildResult(Graph(), (), issues))
        self.assertEqual([entry.status for entry in ledger.entries], ['HELD', 'HELD'])
        self.assertTrue(all((entry.related_reason_codes == ('NOTATION_COLLISION', 'SOURCE_TEXT_TOO_LONG') for entry in ledger.entries)))
        self.assertIs(ledger.blocking, False)
        self.assertIs(ledger.core_complete, False)
        self.assertIs(ledger.whole_release_eligible, False)
        self.assertIs(ledger.release_ineligible, True)

    def test_required_held_reason_classes_are_machine_readable(self) -> None:
        for reason_code, source in [('UNKNOWN_ATOM_SHAPE', 'resolution'), ('CONFLICTING_SEMANTIC_MEANING', 'resolution'), ('SOURCE_IDENTITY_CONFLICT', 'resolution'), ('NOTATION_COLLISION', 'build'), ('NO_PUBLIC_SOURCE_LOCUS', 'build')]:
            with self.subTest(reason_code=reason_code, source=source):
                row = _atom('m1')
                ref = RecordRef('morphemes_atomic', 'm1')
                resource = _resource(Identity('grammar', ('CAT', 'VALUE')), ref)
                resolution_issues = (ResolutionIssue(reason_code, resource.identity.keys, (ref,), ('fixture',)),) if source == 'resolution' else ()
                build_issues = (BuildIssue(reason_code, resource.identity.iri, (ref,), ('fixture',)),) if source == 'build' else ()
                resolved = () if source == 'resolution' else (resource,)
                ledger = _ledger(_closure(_table('morphemes_atomic', row)), Resolution(resolved, resolution_issues), BuildResult(Graph(), (), build_issues))
                self.assertEqual([(entry.status, entry.reason_code) for entry in ledger.entries], [('HELD', reason_code)])
                self.assertIs(ledger.blocking, False)

    def test_future_owner_dispositions_are_explicit_and_nonblocking(self) -> None:
        for status, reason in [('UNSUPPORTED', 'UNSUPPORTED_RELATION'), ('HELD', 'UNADMITTED_MAPPING'), ('REJECTED', 'INVALID_TARGET_REFERENCE')]:
            with self.subTest(status=status, reason=reason):
                row = _atom('m1')
                ref = RecordRef('morphemes_atomic', 'm1')
                semantic_iri = Identity('grammar', ('CAT', 'ATTEMPTED')).iri
                disposition = ExplicitDisposition(ref, status, reason, 'fixture explanation', semantic_iri, ('attempted', 'key'))
                ledger = _ledger(_closure(_table('morphemes_atomic', row)), Resolution((), ()), BuildResult(Graph(), (), ()), explicit_dispositions=(disposition,))
                entry = ledger.entries[0]
                self.assertEqual((entry.status, entry.reason_code, entry.semantic_iri, entry.semantic_key), (status, reason, semantic_iri, ('attempted', 'key')))
                self.assertIs(ledger.blocking, False)
                self.assertIs(ledger.release_ineligible, True)

    def test_repaired_held_row_promotes_to_emitted_without_identity_loss(self) -> None:
        row = _atom('m1')
        ref = RecordRef('morphemes_atomic', 'm1')
        resource = _resource(Identity('grammar', ('CAT', 'VALUE')), ref)
        closure = _closure(_table('morphemes_atomic', row))
        resolution = Resolution((resource,), ())
        held = _ledger(closure, resolution, BuildResult(Graph(), (), (BuildIssue('NO_PUBLIC_SOURCE_LOCUS', resource.identity.iri, (ref,), ()),)))
        repaired = _ledger(closure, resolution, _emitted(resource))
        self.assertEqual(held.entries[0].status, 'HELD')
        self.assertEqual(repaired.entries[0].status, 'EMITTED')
        self.assertTrue(held.entries[0].key == repaired.entries[0].key == 'm1')
        self.assertTrue(held.entries[0].semantic_iri == repaired.entries[0].semantic_iri == resource.identity.iri)

    def test_shuffled_rows_and_reason_order_serialize_identically(self) -> None:
        first, second = (_atom('m1'), _atom('m2'))
        refs = (RecordRef('morphemes_atomic', 'm1'), RecordRef('morphemes_atomic', 'm2'))
        resource = _resource(Identity('grammar', ('CAT', 'VALUE')), *refs)
        a = _ledger(_closure(_table('morphemes_atomic', first, second)), Resolution((resource,), ()), BuildResult(Graph(), (), (BuildIssue('SOURCE_TEXT_TOO_LONG', resource.identity.iri, refs, ('z', 'a')), BuildIssue('NOTATION_COLLISION', resource.identity.iri, refs, ('b',)))))
        b = _ledger(_closure(_table('morphemes_atomic', second, first)), Resolution((resource,), ()), BuildResult(Graph(), (), (BuildIssue('NOTATION_COLLISION', resource.identity.iri, tuple(reversed(refs)), ('b',)), BuildIssue('SOURCE_TEXT_TOO_LONG', resource.identity.iri, tuple(reversed(refs)), ('a', 'z')))))
        self.assertEqual(ledger_json_bytes(a), ledger_json_bytes(b))

    def test_emitted_and_held_for_same_row_is_blocking_and_strong_graph_is_detected(self) -> None:
        row = _atom('m1')
        ref = RecordRef('morphemes_atomic', 'm1')
        resource = _resource(Identity('grammar', ('CAT', 'VALUE')), ref)
        build = _emitted(resource)
        build = BuildResult(build.graph, build.emitted, (BuildIssue('NOTATION_COLLISION', resource.identity.iri, (ref,), ()),))
        ledger = _ledger(_closure(_table('morphemes_atomic', row)), Resolution((resource,), ()), build)
        self.assertEqual(ledger.entries[0].status, 'REJECTED')
        self.assertEqual(ledger.entries[0].reason_code, 'ACCOUNTING_CONFLICT')
        self.assertEqual({item.code for item in ledger.diagnostics}, {'ACCOUNTING_CONFLICT', 'HELD_RESOURCE_IN_STRONG_GRAPH'})
        self.assertIs(ledger.blocking, True)

    def test_missing_semantic_outcome_and_unknown_future_table_fail_closed(self) -> None:
        closure = _closure(_table('morphemes_atomic', _atom('m1')), _table('future_semantics', _row(future_id='future-1', value='x')))
        ledger = _ledger(closure, Resolution((), ()), BuildResult(Graph(), (), ()))
        self.assertEqual([(entry.table, entry.status, entry.reason_code, entry.blocking) for entry in ledger.entries], [('future_semantics', 'UNSUPPORTED', 'UNKNOWN_MANIFEST_TABLE', True), ('morphemes_atomic', 'REJECTED', 'MISSING_SEMANTIC_OUTCOME', True)])
        self.assertEqual({item.code for item in ledger.diagnostics}, {'MISSING_SEMANTIC_OUTCOME', 'UNKNOWN_MANIFEST_TABLE'})
        self.assertIs(ledger.blocking, True)

    def test_group_only_issue_does_not_double_count_member_rows(self) -> None:
        row = _atom('m1')
        ref = RecordRef('morphemes_atomic', 'm1')
        resource = _resource(Identity('grammar', ('CAT', 'VALUE')), ref)
        emitted = _emitted(resource)
        group_iri = Identity('collection', ('fixture-group',)).iri
        group = BuildIssue('COLLECTION_SOURCE_BLOCKED', group_iri, (), ('member=' + resource.identity.iri,))
        ledger = _ledger(_closure(_table('morphemes_atomic', row)), Resolution((resource,), ()), BuildResult(emitted.graph, emitted.emitted, (group,)))
        self.assertEqual([(entry.key, entry.status) for entry in ledger.entries], [('m1', 'EMITTED')])
        self.assertEqual([(item.code, item.resource_iri) for item in ledger.group_issues], [('COLLECTION_SOURCE_BLOCKED', group_iri)])
        self.assertIs(ledger.blocking, False)
        self.assertIs(ledger.release_ineligible, True)

    def test_free_text_diagnostics_are_sanitized_without_rewriting_stable_identity(self) -> None:
        row = _atom('m1')
        ref = RecordRef('morphemes_atomic', 'm1')
        resource = _resource(Identity('grammar', ('CAT', 'VALUE')), ref)
        build = BuildResult(Graph(), (), (BuildIssue('NO_PUBLIC_SOURCE_LOCUS', resource.identity.iri, (ref,), ('file:///Users/example/private.txt', '/Users/example/secret', 'http://localhost:8000/x')),))
        ledger = _ledger(_closure(_table('morphemes_atomic', row)), Resolution((resource,), ()), build)
        serialized = ledger_json_bytes(ledger).decode('utf-8')
        self.assertIn(resource.identity.iri, serialized)
        self.assertNotIn('/Users/example', serialized)
        self.assertNotIn('localhost:8000', serialized)
        self.assertNotIn('file://', serialized)

    def test_duplicate_or_out_of_scope_explicit_dispositions_block_accounting(self) -> None:
        row = _atom('m1')
        ref = RecordRef('morphemes_atomic', 'm1')
        first = ExplicitDisposition(ref, 'HELD', 'UNADMITTED_MAPPING', 'first')
        second = ExplicitDisposition(ref, 'REJECTED', 'INVALID_TARGET_REFERENCE', 'second')
        outside = ExplicitDisposition(RecordRef('morphemes_atomic', 'missing'), 'HELD', 'UNADMITTED_MAPPING', 'outside')
        ledger = _ledger(_closure(_table('morphemes_atomic', row)), Resolution((), ()), BuildResult(Graph(), (), ()), explicit_dispositions=(outside, second, first))
        self.assertEqual(ledger.entries[0].status, 'REJECTED')
        self.assertEqual(ledger.entries[0].reason_code, 'ACCOUNTING_CONFLICT')
        self.assertEqual({item.code for item in ledger.diagnostics}, {'ACCOUNTING_CONFLICT', 'DUPLICATE_EXPLICIT_DISPOSITION', 'EXPLICIT_REF_NOT_IN_CLOSURE'})

    def test_duplicate_closure_key_is_a_blocking_accounting_defect(self) -> None:
        first = _atom('m1', notation='a')
        second = _atom('m1', notation='b')
        ref = RecordRef('morphemes_atomic', 'm1')
        disposition = ExplicitDisposition(ref, 'HELD', 'UNADMITTED_MAPPING', 'fixture')
        ledger = _ledger(_closure(_table('morphemes_atomic', first, second)), Resolution((), ()), BuildResult(Graph(), (), ()), explicit_dispositions=(disposition,))
        self.assertIn('DUPLICATE_ACCOUNTING_REF', {item.code for item in ledger.diagnostics})
        self.assertIs(ledger.blocking, True)

    def test_profile_identity_is_required_before_a_ledger_can_exist(self) -> None:
        closure = _closure(_table('source_manifest', _row(source_id='s1')))
        with self.assertRaises(ProfileError) as version_error:
            build_ledger(closure, Resolution((), ()), BuildResult(Graph(), (), ()), profile_version='', profile_digest=PROFILE_DIGEST)
        self.assertEqual(version_error.exception.code, 'PROFILE_VERSION_REQUIRED')
        with self.assertRaises(ProfileError) as digest_error:
            build_ledger(closure, Resolution((), ()), BuildResult(Graph(), (), ()), profile_version=PROFILE_VERSION, profile_digest='')
        self.assertEqual(digest_error.exception.code, 'PROFILE_DIGEST_REQUIRED')

    def test_literal_fixture_is_byte_stable(self) -> None:
        source = _table('source_manifest', _row(source_id='official-grammar'))
        composition = _table('morpheme_compositions', _row(composition_id='comp-1', primary_source_id='official-grammar'))
        atom = _atom('m1')
        ref = RecordRef('morphemes_atomic', 'm1')
        resource = _resource(Identity('grammar', ('CAT', 'VALUE')), ref)
        ledger = _ledger(_closure(source, _table('morphemes_atomic', atom), composition), Resolution((resource,), ()), _emitted(resource))
        self.assertIs(ledger.core_complete, True)
        self.assertIs(ledger.whole_release_eligible, False)
        self.assertIs(ledger.release_ineligible, True)
        self.assertEqual(ledger_json_bytes(ledger), (FIXTURES / 'skos_ledger_expected.json').read_bytes())

    def test_current_corpus_has_literal_full_accounting_against_core_builder(self) -> None:
        input_root = Path(__file__).resolve().parents[1] / '_data' / 'csv'
        closure = preflight(input_root).require_valid()
        resolution = resolve_identities(closure)
        build = build_core_graph(resolution.resources, SourceProjector(closure))
        ledger = _ledger(closure, resolution, build)
        self.assertEqual((len(resolution.resources), len(build.emitted), len(build.issues), len(build.graph)), (CORE["resolved_resources"], CORE["emitted_resources"], 568, CORE["triple_count"]))
        self.assertEqual(ledger.counts, CORE["ledger_dispositions"])
        self.assertEqual(len(ledger.entries), sum(CORE["ledger_dispositions"].values()))
        self.assertEqual(ledger.diagnostics, ())
        self.assertIs(ledger.blocking, False)
        self.assertIs(ledger.core_complete, False)
        self.assertIs(ledger.whole_release_eligible, False)
        self.assertIs(ledger.release_ineligible, True)
if __name__ == '__main__':
    unittest.main()
