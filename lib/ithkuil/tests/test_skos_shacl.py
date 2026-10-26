from pathlib import Path
import json
import subprocess
import sys
import unittest

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, SKOS

from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.shacl import SHAPES_PATH, validate_graph

BASE = 'https://github.com/Entif-AI/Bilqis-MLX/'
FIXTURES = Path(__file__).parent / 'fixtures'
A = URIRef(BASE + 'id/grammar/TEST/A')
SCHEME = URIRef(BASE + 'id/scheme/new-ithkuil')


def positive():
    return Graph().parse(FIXTURES / 'skos_builder_core.ttl', format='turtle')


class ShaclTests(unittest.TestCase):
    def test_positive_fixture_and_shape_authority_map(self):
        graph = positive()
        before = canonicalize(graph).payload
        result = validate_graph(graph)
        self.assertTrue(result['conforms'], result)
        self.assertEqual(before, canonicalize(graph).payload)
        shapes = Graph().parse(SHAPES_PATH, format='turtle')
        sh = 'http://www.w3.org/ns/shacl#'
        for shape in shapes.subjects(RDF.type, URIRef(sh + 'NodeShape')):
            self.assertTrue(list(shapes.objects(shape, DCTERMS.source)), shape)
            self.assertTrue(list(shapes.objects(shape, DCTERMS.identifier)), shape)

    def test_one_negative_per_invariant(self):
        cases = [
            ('ConceptIdentity', lambda g: g.add((BNode('unstable'), RDF.type, SKOS.Concept))),
            ('SchemeIdentity', lambda g: g.add((URIRef('https://example.invalid/source'), RDF.type, SKOS.ConceptScheme))),
            ('ConceptScheme', lambda g: g.remove((A, SKOS.inScheme, None))),
            ('Notation', lambda g: g.add((A, SKOS.notation, Literal('ẓ', lang='en')))),
            ('PreferredLabels', lambda g: g.add((A, SKOS.prefLabel, Literal('second', lang='en')))),
            ('SourceLinks', lambda g: g.remove((A, DCTERMS.source, None))),
            ('NoCurriculum', lambda g: g.add((URIRef('urn:orphan'), URIRef(BASE + 'vocab/curriculumOrder'), Literal(1)))),
            ('MappingEndpoints', lambda g: g.add((A, SKOS.exactMatch, SCHEME))),
        ]
        for name, mutate in cases:
            with self.subTest(name=name):
                graph = positive()
                mutate(graph)
                result = validate_graph(graph)
                self.assertFalse(result['conforms'])
                failures = [v for v in result['violations'] if v['shape'].endswith('/' + name)]
                self.assertTrue(failures, result)
                for failure in failures:
                    self.assertTrue(failure['focus_node'])
                    self.assertTrue(failure['invariant'])
                    self.assertTrue(failure['owners'])

    def test_absent_mapping_admission_fails_closed_and_explicit_support_passes(self):
        graph = positive()
        b = URIRef(BASE + 'id/grammar/TEST/B')
        secondary = URIRef(BASE + 'id/scheme/fixture-secondary')
        graph.remove((A, SKOS.inScheme, SCHEME))
        graph.remove((b, SKOS.inScheme, secondary))
        triple = (A, SKOS.closeMatch, b)
        graph.add(triple)
        rejected = validate_graph(graph)
        self.assertFalse(rejected['conforms'])
        self.assertIn('MappingAdmission', {v['invariant'] for v in rejected['violations']})
        self.assertTrue(validate_graph(graph, admitted_mappings=(triple,))['conforms'])

    def test_notation_accepts_exact_unicode_and_rejects_untyped_or_unknown(self):
        for value in [Literal('∅', datatype=URIRef(BASE + 'id/datatype/new-ithkuil')),
                      Literal('z\u0307', datatype=URIRef(BASE + 'id/datatype/new-ithkuil'), normalize=False)]:
            graph = positive()
            graph.add((A, SKOS.notation, value))
            self.assertTrue(validate_graph(graph)['conforms'])
        for value in [Literal('x'), Literal('x', datatype=URIRef('urn:unknown'))]:
            graph = positive()
            graph.add((A, SKOS.notation, value))
            self.assertFalse(validate_graph(graph)['conforms'])

    def test_standalone_command_success_and_failure(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'canonical.nt'
            for expected, graph in [(0, positive()), (2, Graph().add((A, RDF.type, SKOS.Concept)))]:
                path.write_bytes(canonicalize(graph).payload)
                result = subprocess.run([sys.executable, '-m', 'lib.ithkuil.src.skos.shacl', '--rdf', str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report['conforms'], expected == 0)
                self.assertEqual(report['canonical_sha256'], canonicalize(graph).sha256)
