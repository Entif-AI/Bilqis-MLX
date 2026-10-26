from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid

from rdflib import Graph,Literal,URIRef
from rdflib.namespace import SKOS

from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.conformance import validate_artifacts,write_evidence
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.falkor_import import Importer,connect
from lib.ithkuil.src.skos.falkor_lookup import Reader
from lib.ithkuil.src.skos.falkor_smoke import run_smoke,SUITE_PATH
from lib.ithkuil.src.skos.mapping_admission import load_policy
from lib.ithkuil.src.skos.mapping_emit import emit_admitted_mappings
from lib.ithkuil.src.skos.publication import json_bytes
from lib.ithkuil.tests.test_skos_conformance import fixture
from lib.ithkuil.tests.test_skos_mapping_emit import reviewed_row
from lib.ithkuil.tests.test_skos_shacl import A,BASE,SCHEME


def smoke_evidence(directory):
    graph,coverage,rows=fixture();b=URIRef(BASE+'id/grammar/TEST/B');secondary=URIRef(BASE+'id/scheme/fixture-secondary')
    graph.remove((A,SKOS.inScheme,SCHEME));graph.remove((b,SKOS.prefLabel,None));graph.add((b,SKOS.prefLabel,Literal('Alpha',lang='en')))
    graph.add((A,SKOS.related,b))
    reviewed=reviewed_row('admitted-close',str(A),str(b),str(secondary),str(SCHEME),'closeMatch','admitted_close_match')
    held=replace(reviewed,record_ref=replace(reviewed.record_ref,key='held-exact'),claim=replace(reviewed.claim,predicate='exactMatch',review_state='proposal'))
    emission=emit_admitted_mappings((reviewed,held),graph,load_policy())
    assert len(emission.graph)==2 and held.record_ref in emission.held_records
    for triple in emission.graph:graph.add(triple)
    root=URIRef(BASE+'id/root/NI-WEB-CH02/ROOT-FIXTURE');sense=URIRef(BASE+'id/sense/NI-WEB-CH02/ROOT-FIXTURE/STEM%201/BSC')
    graph.add((root,URIRef(BASE+'vocab/hasSense'),sense));graph.add((sense,URIRef(BASE+'vocab/lexiconStem'),Literal('STEM 1')));graph.add((sense,URIRef(BASE+'vocab/lexiconSpecification'),Literal('BSC')))
    canonical=canonicalize(graph);coverage['canonical_rdf']={'sha256':canonical.sha256,'triple_count':len(graph)}
    report=validate_artifacts(graph,coverage,rows,graph,admitted_mappings=emission.graph)
    assert report['status']=='complete',report
    files={'canonical.nt':canonical.payload,'comparison.nt':canonical.payload,'coverage.json':json_bytes(coverage),'source-rows.json':json_bytes([{'domain':r.domain,'table':r.table,'key':r.key} for r in rows]),'conformance.json':json_bytes(report),'admitted-mappings.nt':canonicalize(emission.graph).payload}
    return Path(write_evidence(files,directory)['path'])


class SmokeSuiteTests(unittest.TestCase):
    def test_mutation_is_rejected_before_query_execution(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json';suite=json.loads(SUITE_PATH.read_text());suite['queries'][0]['cypher']='CREATE (n)';p.write_text(json.dumps(suite))
            reader=Mock()
            with self.assertRaises(ProfileError):run_smoke(reader,p)
            reader.query.assert_not_called()

    def test_duplicate_query_identity_is_rejected_before_execution(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'duplicate.json';suite=json.loads(SUITE_PATH.read_text())
            suite['queries'][1]['id']=suite['queries'][0]['id'];p.write_text(json.dumps(suite))
            reader=Mock()
            with self.assertRaises(ProfileError):run_smoke(reader,p)
            reader.query.assert_not_called()

    def test_missing_required_query_cannot_claim_a_complete_suite(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'missing.json';suite=json.loads(SUITE_PATH.read_text());suite['queries'].pop()
            p.write_text(json.dumps(suite));reader=Mock()
            with self.assertRaises(ProfileError):run_smoke(reader,p)
            reader.query.assert_not_called()

    @unittest.skipUnless(os.environ.get('BILQIS_FALKOR_LIVE')=='1','explicit isolated live proof only')
    def test_frozen_suite_on_fresh_conformant_import(self):
        name='bilqis_skos_19_77_'+uuid.uuid4().hex[:12];owner='smoke-'+uuid.uuid4().hex
        print(json.dumps({'live_graph':name,'owner':owner}),flush=True)
        with tempfile.TemporaryDirectory() as d:
            i=Importer(connect(),name,owner);i.materialize(smoke_evidence(d));before=i.read_projection()
            report=run_smoke(Reader(i));self.assertTrue(report['passed'],report)
            self.assertEqual(len(report['cases']),11)
            from redis.exceptions import ResponseError
            with self.assertRaises(ResponseError):Reader(i).query('CREATE (n:ForbiddenWrite)')
            self.assertEqual(i.read_projection(),before)
            print(json.dumps({'passed':report['passed'],'cases':len(report['cases']),'digest':report['canonical_sha256']},sort_keys=True))
