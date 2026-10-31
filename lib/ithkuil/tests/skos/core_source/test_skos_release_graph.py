from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
"""Release fixture and reset/rebuild receipt equivalence contracts."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
import tempfile
import hashlib
from unittest.mock import patch

from lib.ithkuil.tests.release_graph_proof import comparable_receipt, fixture_preflight, prove
from lib.ithkuil.src.skos.errors import ProfileError
from rdflib import Graph
from lib.ithkuil.src.skos.falkor_smoke import MUTATION, REQUIRED_CASES


class ReleaseGraphTests(unittest.TestCase):
    def test_release_fixture_is_read_only_and_has_a_real_admitted_relation(self):
        suite = json.loads((FIXTURES / 'release95_smoke.json').read_text())
        self.assertEqual({q['id'] for q in suite['queries']}, REQUIRED_CASES)
        self.assertEqual(suite['canonical_rdf_sha256'],
                         '7a0a0cd04133be41db69ca3fe1e2f09b4efbc8c965610b75c5ac30bc0954b50e')
        queries = {q['id']: q for q in suite['queries']}
        self.assertEqual(queries['grammar-code']['expected'],
                         [['https://github.com/Entif-AI/Bilqis-MLX/id/grammar/BIAS/ACC']])
        self.assertEqual(queries['utf8-notation']['params']['lexical'], 'cč')
        self.assertEqual(queries['utf8-notation']['expected'],
                         [['https://github.com/Entif-AI/Bilqis-MLX/id/grammar/BIAS/DFD']])
        self.assertTrue(queries['root-sense-dimensions']['expected'])
        self.assertEqual(queries['admitted-cross-scheme']['expected'], [])
        self.assertTrue(all(MUTATION.search(q['cypher']) is None for q in suite['queries']))

    def test_empty_lookup_fixture_fails_before_external_mutation(self):
        suite = json.loads((FIXTURES / 'release95_smoke.json').read_text())
        suite['queries'][0]['expected'] = []
        with self.assertRaises(ProfileError) as caught:
            fixture_preflight(Graph(), suite)
        self.assertEqual(caught.exception.code, 'RELEASE95_LOOKUP_EXPECTATION_EMPTY')

    def test_bad_fixture_prevents_opening_the_graph_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / 'bundle'
            bundle.mkdir()
            (bundle / 'canonical.nt').write_bytes(b'')
            digest = hashlib.sha256(b'').hexdigest()
            suite = json.loads((FIXTURES / 'release95_smoke.json').read_text())
            suite['queries'][0]['expected'] = []
            suite['canonical_rdf_sha256'] = digest
            suite_path = root / 'suite.json'
            suite_path.write_text(json.dumps(suite))
            session_path = root / 'session.json'
            session_path.write_text(json.dumps({'graph': 'bilqis_skos_release95_fixture',
                'owner': 'codex_release95_fixture', 'canonical_sha256': digest,
                'suite_sha256': hashlib.sha256(suite_path.read_bytes()).hexdigest()}))
            census_path = root / 'census.json'
            census_path.write_text(json.dumps({'accounting_complete': True, 'canonical_rdf': {'sha256': digest}}))
            with patch('lib.ithkuil.tests.release_graph_proof.connect') as connect:
                with self.assertRaises(ProfileError) as caught:
                    prove(session_path, bundle, suite_path, census_path, root / 'output')
                self.assertEqual(caught.exception.code, 'RELEASE95_LOOKUP_EXPECTATION_EMPTY')
                connect.assert_not_called()
            self.assertFalse((root / 'output').exists())

    def test_only_timestamp_may_differ_between_same_projection_receipts(self):
        first = {'timestamp': 'first', 'canonical_rdf_sha256': 'a' * 64,
                 'nodes_by_label': {'RdfTerm': 2}, 'edges_by_type': {'RDF': 3},
                 'smoke_suite': {'passed': True}, 'coverage_status': 'partial'}
        second = {**first, 'timestamp': 'second'}
        self.assertEqual(comparable_receipt(first), comparable_receipt(second))
        for changed in ({**second, 'edges_by_type': {'RDF': 4}},
                        {**second, 'coverage_status': 'complete'},
                        {**second, 'canonical_rdf_sha256': 'b' * 64}):
            self.assertNotEqual(comparable_receipt(first), comparable_receipt(changed))


if __name__ == '__main__':
    unittest.main()
