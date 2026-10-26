"""Exact read-only lookup shapes; indexes never determine semantic truth (#76)."""
from __future__ import annotations

from rdflib.namespace import SKOS

from .errors import ProfileError
from .identity import BASE

INDEXES=(('RdfTerm','iri'),('RdfTerm','lexical'),('RdfTerm','datatype'))


def ensure_indexes(importer):
    state=importer.require_owned()
    if state['state']!='complete':raise ProfileError('FALKOR_PROJECTION_INCOMPLETE')
    present=importer._read('CALL db.indexes() YIELD label, properties RETURN label,properties')
    for label,field in INDEXES:
        if not any(found_label==label and field in fields for found_label,fields in present):
            importer.graph.query(f'CREATE INDEX FOR (n:{label}) ON (n.{field})')
    return {'indexes':[{'label':label,'property':field} for label,field in INDEXES]}


class Reader:
    def __init__(self,importer):
        self._importer=importer
        state=importer.require_owned()
        if state['state']!='complete':raise ProfileError('FALKOR_PROJECTION_INCOMPLETE')
        self.graph_name,self.owner,self.canonical_sha256=importer.name,importer.owner,state['digest']

    def query(self,query,params=None):
        state=self._importer.require_owned()
        if state['state']!='complete' or state['digest']!=self.canonical_sha256:
            raise ProfileError('FALKOR_READER_ARTIFACT_CHANGED')
        # Enforcement occurs at GRAPH.RO_QUERY, including caller-provided Cypher.
        return self._importer._read(query,{**(params or {}),'owner':self.owner})

    def by_iri(self,iri):
        rows=self.query('MATCH(n:RdfTerm) WHERE n.owner=$owner AND n.iri=$iri RETURN n.key,n.iri ORDER BY n.key',{'iri':iri})
        if len(rows)>1:raise ProfileError('FALKOR_IRI_LOOKUP_NOT_UNIQUE',iri)
        return [row[1] for row in rows]

    def notation(self,lexical,datatype):
        if datatype not in {BASE+'id/datatype/new-ithkuil',BASE+'id/datatype/grammar-code'}:
            raise ProfileError('FALKOR_NOTATION_SYSTEM_UNSUPPORTED',datatype)
        return [r[0] for r in self.query('MATCH(s:RdfTerm)-[r:RDF]->(v:RdfTerm) WHERE s.owner=$owner AND r.owner=$owner AND v.owner=$owner AND r.predicate_iri=$predicate AND v.lexical=$lexical AND v.datatype=$datatype AND v.language=$language RETURN DISTINCT s.iri ORDER BY s.iri',{'predicate':str(SKOS.notation),'lexical':lexical,'datatype':datatype,'language':''})]

    def label_candidates(self,label,language):
        return [r[0] for r in self.query('MATCH(s:RdfTerm)-[r:RDF]->(v:RdfTerm) WHERE s.owner=$owner AND r.owner=$owner AND v.owner=$owner AND r.predicate_iri=$predicate AND v.lexical=$label AND v.language=$language RETURN DISTINCT s.iri ORDER BY s.iri',{'predicate':str(SKOS.prefLabel),'label':label,'language':language})]

    def scheme(self,iri):
        return [r[0] for r in self.query('MATCH(s:RdfTerm)-[r:RDF]->(v:RdfTerm) WHERE s.owner=$owner AND r.owner=$owner AND v.owner=$owner AND r.predicate_iri=$predicate AND v.iri=$iri RETURN DISTINCT s.iri ORDER BY s.iri',{'predicate':str(SKOS.inScheme),'iri':iri})]

    def members(self,iri):
        return [r[0] for r in self.query('MATCH(s:RdfTerm)-[r:RDF]->(v:RdfTerm) WHERE s.owner=$owner AND r.owner=$owner AND v.owner=$owner AND r.predicate_iri=$predicate AND s.iri=$iri RETURN DISTINCT v.iri ORDER BY v.iri',{'predicate':str(SKOS.member),'iri':iri})]
