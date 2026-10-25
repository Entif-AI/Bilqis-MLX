import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from rdflib import Literal
from rdflib.namespace import SKOS

from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.conformance import GATES, validate_artifacts
from lib.ithkuil.src.skos.coverage import compose_coverage
from lib.ithkuil.src.skos.no_omission import SourceRowIdentity
from lib.ithkuil.tests.test_skos_coverage import _clean_domain, CLEAN
from lib.ithkuil.tests.test_skos_shacl import positive, A


def fixture():
    graph = positive()
    domains = {name: _clean_domain(name, row) for name, row in CLEAN['rows'].items()}
    coverage = compose_coverage(domains, CLEAN['inputs'], (graph,), profile_version='bilqis-skos-profile/1', profile_sha256='a' * 64).receipt
    rows = tuple(SourceRowIdentity(name, row['table'], row['key']) for name, row in CLEAN['rows'].items())
    return graph, coverage, rows


class ConformanceTests(unittest.TestCase):
    def test_clean_fixture_runs_registered_gates_and_keeps_evidence(self):
        graph, receipt, rows = fixture()
        result = validate_artifacts(graph, receipt, rows, graph)
        self.assertEqual(tuple(g['gate'] for g in result['gates']), GATES)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['failed_gates'], [])
        for gate in result['gates']:
            self.assertEqual(gate['status'], 'passed')
            self.assertTrue(gate['version'])
            self.assertTrue(gate['evidence'])

    def test_each_constituent_failure_remains_named(self):
        for target in GATES:
            with self.subTest(target=target):
                graph, receipt, rows = fixture()
                comparison = graph
                if target == 'coverage':
                    receipt['totals']['source_rows'] += 1
                elif target == 'no-omission':
                    rows = rows + (SourceRowIdentity('atomic', 'morphemes_atomic', 'MISSING'),)
                elif target == 'determinism':
                    comparison = positive()
                    comparison.add((A, SKOS.note, Literal('intentional semantic mutation')))
                elif target == 'shacl':
                    graph.add((A, SKOS.notation, Literal('untyped')))
                    receipt['canonical_rdf'] = {'sha256': canonicalize(graph).sha256, 'triple_count': len(graph)}
                    comparison = graph
                result = validate_artifacts(graph, receipt, rows, comparison)
                self.assertEqual(result['status'], 'failed')
                self.assertIn(target, result['failed_gates'])
                failed = next(g for g in result['gates'] if g['gate'] == target)
                self.assertTrue(failed['evidence'])

    def test_receipt_rdf_binding_is_verified(self):
        graph, receipt, rows = fixture()
        receipt['canonical_rdf']['sha256'] = '0' * 64
        result = validate_artifacts(graph, receipt, rows, graph)
        self.assertIn('coverage', result['failed_gates'])

    def test_gate_infrastructure_failure_is_distinct_and_named(self):
        graph, receipt, rows = fixture()
        with patch('lib.ithkuil.src.skos.conformance.validate_graph', side_effect=OSError):
            result = validate_artifacts(graph, receipt, rows, graph)
        self.assertEqual(result['status'], 'infrastructure-failed')
        self.assertEqual(result['failed_gates'], ['shacl'])

    def test_registry_cannot_silently_drop_a_mandatory_gate(self):
        self.assertEqual(GATES, ('coverage', 'no-omission', 'determinism', 'shacl'))

    def test_cli_preserves_json_and_human_summary_and_distinguishes_io_failure(self):
        graph, receipt, rows = fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'canonical.nt').write_bytes(canonicalize(graph).payload)
            (root / 'coverage.json').write_text(json.dumps(receipt))
            (root / 'source-rows.json').write_text(json.dumps([{'domain': r.domain, 'table': r.table, 'key': r.key} for r in rows]))
            command = [sys.executable, '-m', 'lib.ithkuil.src.skos.conformance', '--rdf', str(root/'canonical.nt'), '--coverage', str(root/'coverage.json'), '--source-rows', str(root/'source-rows.json'), '--comparison-rdf', str(root/'canonical.nt'), '--output-root', str(root/'reports')]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], 'complete')
            self.assertIn('4/4', result.stderr)
            evidence = Path(json.loads(result.stdout)['evidence']['path'])
            self.assertEqual((evidence / 'canonical.nt').read_bytes(), canonicalize(graph).payload)
            self.assertEqual((evidence / 'admitted-mappings.nt').read_bytes(), b'')
            repeated = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertEqual(repeated.stdout, result.stdout)
            (root / 'canonical.nt').unlink()
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 3)
            self.assertEqual(json.loads(result.stdout)['status'], 'infrastructure-failed')
