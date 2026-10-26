"""Lossless RDF 1.1 default-graph projection contract for FalkorDB (#73)."""
from __future__ import annotations

import hashlib
import json

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import RDF, SKOS

from .canonical import canonicalize
from .errors import ProfileError
from .rdf_read import read_canonical_graph

SCHEMA = 'bilqis.skos.falkor-projection/v1'
VERSION = '1.0.0'
TYPE_LABELS = {SKOS[name]: name for name in ('Concept', 'ConceptScheme', 'Collection', 'OrderedCollection')}


def _key(parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def _node(term, graph_digest):
    if isinstance(term, URIRef):
        return {'key': _key(['iri', str(term)]), 'kind': 'iri', 'iri': str(term), 'labels': ['RdfTerm', 'Resource']}
    if isinstance(term, BNode):
        return {'key': _key(['bnode', graph_digest, str(term)]), 'kind': 'bnode', 'blank_id': str(term), 'labels': ['BlankNode', 'RdfTerm']}
    if isinstance(term, Literal):
        lexical, datatype, language = str(term), str(term.datatype or ''), term.language or ''
        return {'key': _key(['literal', lexical, datatype, language]), 'kind': 'literal', 'lexical': lexical,
                'datatype': datatype, 'language': language, 'labels': ['Literal', 'RdfTerm']}
    raise ProfileError('FALKOR_UNSUPPORTED_RDF_TERM', type(term).__name__)


def project_graph(graph: Graph) -> dict:
    canonical = canonicalize(graph)
    graph = read_canonical_graph(canonical.payload)
    nodes, edges = {}, {}
    for subject, predicate, target in graph:
        for term in (subject, target):
            node = _node(term, canonical.sha256)
            previous = nodes.setdefault(node['key'], node)
            if previous != node:
                raise ProfileError('FALKOR_TERM_KEY_COLLISION', node['key'])
        source_key = _node(subject, canonical.sha256)['key']
        target_key = _node(target, canonical.sha256)['key']
        edge_key = _key(['triple', source_key, str(predicate), target_key])
        edges[edge_key] = {'key': edge_key, 'source': source_key, 'target': target_key,
                           'predicate_iri': str(predicate), 'type': 'RDF'}
    for subject, _, target in graph.triples((None, RDF.type, None)):
        if target in TYPE_LABELS:
            node = nodes[_node(subject, canonical.sha256)['key']]
            node['labels'] = sorted(set(node['labels']) | {TYPE_LABELS[target]})
    return {'schema': SCHEMA, 'version': VERSION, 'canonical_sha256': canonical.sha256,
            'triple_count': canonical.triple_count,
            'nodes': sorted(nodes.values(), key=lambda n: n['key']),
            'edges': sorted(edges.values(), key=lambda e: e['key'])}


def reconstruct_graph(projection: dict) -> Graph:
    """Recompute graph digest, term/edge identities, labels and complete accounting."""
    try:
        if projection['schema'] != SCHEMA or projection['version'] != VERSION:
            raise ProfileError('FALKOR_PROJECTION_VERSION_UNSUPPORTED')
        terms = {}
        for node in projection['nodes']:
            kind = node['kind']
            if kind == 'iri':
                term = URIRef(node['iri'])
            elif kind == 'bnode':
                term = BNode(node['blank_id'])
            elif kind == 'literal':
                if node['datatype'] and node['language']:
                    raise ProfileError('FALKOR_LITERAL_DATATYPE_AND_LANGUAGE')
                term = Literal(node['lexical'], datatype=URIRef(node['datatype']) if node['datatype'] else None,
                               lang=node['language'] or None, normalize=False)
            else:
                raise ProfileError('FALKOR_UNSUPPORTED_TERM_KIND', str(kind))
            if node['key'] in terms:
                raise ProfileError('FALKOR_DUPLICATE_TERM_KEY', node['key'])
            terms[node['key']] = term
        graph = Graph()
        for edge in projection['edges']:
            graph.add((terms[edge['source']], URIRef(edge['predicate_iri']), terms[edge['target']]))
        expected = project_graph(graph)
        normalized = {**projection, 'nodes': sorted(projection['nodes'], key=lambda n: n['key']),
                      'edges': sorted(projection['edges'], key=lambda e: e['key'])}
        if normalized != expected:
            raise ProfileError('FALKOR_PROJECTION_ROUNDTRIP_MISMATCH')
        return graph
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, ProfileError):
            raise
        raise ProfileError('FALKOR_PROJECTION_MALFORMED', type(error).__name__) from error
