from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
from pathlib import Path
import unittest
import json

from rdflib import BNode, Dataset, Graph, Literal, URIRef
from rdflib.namespace import RDF, SKOS

from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.falkor_projection import project_graph, reconstruct_graph
from lib.ithkuil.tests.skos.conformance.test_skos_shacl import positive, A


class FalkorProjectionTests(unittest.TestCase):
    def test_golden_notation_has_literal_node_and_exact_predicate(self):
        graph = Graph().add((A, SKOS.notation, Literal('ẓ', datatype=URIRef('urn:notation'), normalize=False)))
        result = project_graph(graph)
        expected = json.loads((FIXTURES / 'falkor_projection_expected.json').read_text())
        self.assertEqual(result, expected)
        self.assertEqual(len(result['nodes']), 2)
        resource = next(n for n in result['nodes'] if n['kind'] == 'iri')
        literal = next(n for n in result['nodes'] if n['kind'] == 'literal')
        self.assertEqual(resource['iri'], str(A))
        self.assertEqual(literal['lexical'], 'ẓ')
        self.assertEqual(literal['datatype'], 'urn:notation')
        self.assertEqual(literal['language'], '')
        self.assertEqual(result['edges'], [{'key': result['edges'][0]['key'], 'source': resource['key'], 'target': literal['key'], 'predicate_iri': str(SKOS.notation), 'type': 'RDF'}])
        self.assertEqual(canonicalize(reconstruct_graph(result)).payload, canonicalize(graph).payload)

    def test_all_core_shapes_and_unknown_predicates_roundtrip_losslessly(self):
        graph = positive()
        graph.add((A, URIRef('urn:unknown:predicate'), Literal('opaque, preserved without interpretation')))
        result = project_graph(graph)
        self.assertEqual(len(result['edges']), len(graph))
        self.assertEqual(canonicalize(reconstruct_graph(result)).payload, canonicalize(graph).payload)
        concept = next(n for n in result['nodes'] if n.get('iri') == str(A))
        self.assertIn('Concept', concept['labels'])
        self.assertEqual(result, project_graph(graph))
        self.assertFalse(any('graph_name' in n or 'id' in n for n in result['nodes']))

    def test_blank_node_order_and_exact_typed_lexical_forms_survive(self):
        graph = Graph()
        head = BNode('source-local-list')
        graph.add((A, SKOS.memberList, head))
        graph.add((head, RDF.first, Literal('01', datatype=URIRef('http://www.w3.org/2001/XMLSchema#integer'), normalize=False)))
        graph.add((head, RDF.rest, RDF.nil))
        result = project_graph(graph)
        self.assertEqual(canonicalize(reconstruct_graph(result)).payload, canonicalize(graph).payload)
        self.assertIn('01', [n.get('lexical') for n in result['nodes']])
        renamed = Graph()
        for s, p, o in graph:
            renamed.add((BNode('other') if s == head else s, p, BNode('other') if o == head else o))
        self.assertEqual(project_graph(renamed), result)

    def test_named_graph_and_invalid_terms_are_rejected(self):
        with self.assertRaises(ProfileError):
            project_graph(Dataset())
        graph = Graph().add((URIRef('relative'), SKOS.note, Literal('bad')))
        with self.assertRaises(ProfileError):
            project_graph(graph)

    def test_damaged_projection_cannot_claim_roundtrip_equivalence(self):
        result = project_graph(positive())
        result['edges'].pop()
        with self.assertRaises(ProfileError):
            reconstruct_graph(result)
