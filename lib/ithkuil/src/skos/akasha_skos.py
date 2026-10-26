"""Bounded Akasha-facing read adapter over an explicit Bilqis projection (#79)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rdflib import Literal,URIRef
from rdflib.namespace import RDF,SKOS

from .errors import ProfileError
from .falkor_import import Importer,connect
from .falkor_lookup import Reader
from .falkor_receipt import validate_receipt,verify_receipt
from .rdf_read import read_canonical_graph

NEIGHBORS=frozenset(SKOS[n] for n in ('related','broader','narrower','exactMatch','closeMatch','broadMatch','narrowMatch','relatedMatch'))


class AkashaSkosClient:
    def __init__(self,db,graph,owner,receipt,bundle,suite):
        validate_receipt(receipt)
        if receipt['status']!='complete':raise ProfileError('AKASHA_SKOS_RECEIPT_INCOMPLETE')
        if receipt['graph']!=graph or receipt['owner']!=owner:
            raise ProfileError('AKASHA_SKOS_PROJECTION_MISMATCH')
        self._importer=Importer(db,graph,owner)
        self._reader=Reader(self._importer)
        self._receipt=receipt;self._bundle=Path(bundle);self._suite=Path(suite)

    def read(self,lexical,datatype,*,expected_iri):
        verify_receipt(self._receipt,self._importer,self._bundle,self._suite)
        graph=read_canonical_graph((self._bundle/'canonical.nt').read_bytes())
        subject=URIRef(expected_iri)
        if (subject,RDF.type,SKOS.Concept) not in graph:
            raise ProfileError('AKASHA_SKOS_EXPECTED_CONCEPT_MISSING',expected_iri)
        candidates=self._reader.notation(lexical,datatype)
        canonical_candidates=sorted(str(s) for s in graph.subjects(SKOS.notation,Literal(lexical,datatype=URIRef(datatype),normalize=False)))
        if candidates!=canonical_candidates:raise ProfileError('AKASHA_SKOS_NOTATION_DRIFT')
        if expected_iri not in candidates:raise ProfileError('AKASHA_SKOS_EXPECTED_CONCEPT_MISSING',expected_iri)
        params={'iri':expected_iri,'member':str(SKOS.member),'scheme':str(SKOS.inScheme),'neighbors':sorted(map(str,NEIGHBORS))}
        schemes=[r[0] for r in self._reader.query('MATCH(s:RdfTerm)-[r:RDF]->(t:RdfTerm) WHERE s.owner=$owner AND r.owner=$owner AND t.owner=$owner AND s.iri=$iri AND r.predicate_iri=$scheme RETURN DISTINCT t.iri ORDER BY t.iri',params)]
        families=[r[0] for r in self._reader.query('MATCH(f:RdfTerm)-[r:RDF]->(s:RdfTerm) WHERE f.owner=$owner AND r.owner=$owner AND s.owner=$owner AND s.iri=$iri AND r.predicate_iri=$member RETURN DISTINCT f.iri ORDER BY f.iri',params)]
        neighbors=[{'predicate_iri':r[0],'target_iri':r[1]} for r in self._reader.query('MATCH(s:RdfTerm)-[r:RDF]->(t:RdfTerm) WHERE s.owner=$owner AND r.owner=$owner AND t.owner=$owner AND s.iri=$iri AND r.predicate_iri IN $neighbors RETURN DISTINCT r.predicate_iri,t.iri ORDER BY r.predicate_iri,t.iri',params)]
        expected_schemes=sorted(map(str,graph.objects(subject,SKOS.inScheme)))
        expected_families=sorted(map(str,graph.subjects(SKOS.member,subject)))
        expected_neighbors=sorted([{'predicate_iri':str(p),'target_iri':str(o)} for _,p,o in graph.triples((subject,None,None)) if p in NEIGHBORS],key=lambda n:(n['predicate_iri'],n['target_iri']))
        if (schemes,families,neighbors)!=(expected_schemes,expected_families,expected_neighbors):
            raise ProfileError('AKASHA_SKOS_CANONICAL_READ_MISMATCH')
        return {'schema':'bilqis.akasha.skos-read/v1','graph':self._importer.name,'owner':self._importer.owner,
                'canonical_rdf_sha256':self._receipt['canonical_rdf_sha256'],'concept_iri':expected_iri,
                'notation':{'lexical':lexical,'datatype':datatype},'candidate_iris':candidates,
                'schemes':schemes,'families':families,'neighbors':neighbors,
                'coverage_status':self._receipt['coverage_status']}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graph',required=True);parser.add_argument('--owner',required=True)
    parser.add_argument('--receipt',type=Path,required=True);parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--suite',type=Path,required=True);parser.add_argument('--notation',required=True)
    parser.add_argument('--datatype',required=True);parser.add_argument('--expected-iri',required=True)
    parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=16379)
    a=parser.parse_args(argv)
    try:
        client=AkashaSkosClient(connect(a.host,a.port),a.graph,a.owner,json.loads(a.receipt.read_text()),a.bundle,a.suite)
        result=client.read(a.notation,a.datatype,expected_iri=a.expected_iri)
    except Exception as error:
        print(json.dumps({'status':'failed','code':getattr(error,'code',type(error).__name__)}));return 2
    print(json.dumps(result,ensure_ascii=False,sort_keys=True));return 0


if __name__=='__main__':raise SystemExit(main())
