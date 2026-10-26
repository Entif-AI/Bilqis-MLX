import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
import subprocess
import sys
from unittest.mock import Mock
from redis.exceptions import ConnectionError as RedisConnectionError

from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.conformance import validate_artifacts, write_evidence
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.falkor_import import Importer, load_conformant_bundle, connect
from lib.ithkuil.src.skos.publication import json_bytes
from lib.ithkuil.tests.test_skos_conformance import fixture


def evidence(root):
    graph, receipt, rows = fixture()
    report = validate_artifacts(graph, receipt, rows, graph)
    files = {'canonical.nt':canonicalize(graph).payload, 'comparison.nt':canonicalize(graph).payload,
             'coverage.json':json_bytes(receipt),'source-rows.json':json_bytes([{'domain':r.domain,'table':r.table,'key':r.key} for r in rows]),'conformance.json':json_bytes(report)}
    return Path(write_evidence(files, root)['path'])


class ImportPreflightTests(unittest.TestCase):
    def test_verified_bundle_and_tampered_canonical_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            root=evidence(d)
            projection=load_conformant_bundle(root)
            self.assertGreater(projection['triple_count'],0)
            (root/'canonical.nt').write_bytes(b'')
            with self.assertRaises(ProfileError): load_conformant_bundle(root)

    def test_aggregate_cli_export_is_independently_importable(self):
        with tempfile.TemporaryDirectory() as d:
            source=evidence(Path(d)/'source')
            command=[sys.executable,'-m','lib.ithkuil.src.skos.conformance',
                     '--rdf',str(source/'canonical.nt'),'--coverage',str(source/'coverage.json'),
                     '--source-rows',str(source/'source-rows.json'),'--comparison-rdf',str(source/'comparison.nt'),
                     '--output-root',str(Path(d)/'export')]
            run=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)
            exported=Path(json.loads(run.stdout)['evidence']['path'])
            self.assertEqual(load_conformant_bundle(exported),load_conformant_bundle(source))

    def test_public_import_cannot_bypass_conformance_with_a_projection_dict(self):
        importer=Importer(Mock(),'bilqis_test','test-owner')
        with self.assertRaises(ProfileError): importer.materialize({'schema':'invented'})

    def test_failed_gate_cannot_be_presented_as_conformant(self):
        with tempfile.TemporaryDirectory() as d:
            root=evidence(d)
            p=root/'conformance.json'; r=json.loads(p.read_text());r['gates'].pop();p.write_text(json.dumps(r))
            with self.assertRaises(ProfileError): load_conformant_bundle(root)


@unittest.skipUnless(os.environ.get('BILQIS_FALKOR_LIVE') == '1','explicit isolated live proof only')
class LiveImportTests(unittest.TestCase):
    def test_empty_import_repeat_and_interrupted_resume(self):
        db=connect()
        name='bilqis_skos_19_74_'+uuid.uuid4().hex[:12]
        owner='issue74-'+uuid.uuid4().hex
        self.assertNotIn(name,db.list_graphs())
        print(json.dumps({'live_graph':name,'owner':owner}),flush=True)
        with tempfile.TemporaryDirectory() as d:
            bundle=evidence(d)
            projection=load_conformant_bundle(bundle)
            importer=Importer(db,name,owner,batch_size=5)
            with self.assertRaises(ProfileError): importer.materialize(bundle,fail_after_batches=1)
            self.assertEqual(importer.status()['state'],'incomplete')
            importer.graph.query('CREATE INDEX FOR (n:RdfTerm) ON (n.iri)')
            first=importer.materialize(bundle)
            second=importer.materialize(bundle)
            self.assertEqual(first,second)
            self.assertEqual(importer.read_projection(),projection)
            self.assertEqual(second['status'],'complete')
            print(json.dumps({'live_graph':name,'owner':owner,'proof':'import-repeat-interrupted-resume','receipt':second},sort_keys=True))

    def test_lost_completion_ack_is_reconciled_without_duplicate_import(self):
        db=connect(); name='bilqis_skos_19_74_ack_'+uuid.uuid4().hex[:10]; owner='ack-'+uuid.uuid4().hex
        print(json.dumps({'live_graph':name,'owner':owner}),flush=True)
        importer=Importer(db,name,owner)
        original=importer.graph.query
        def lose_ack(query,params=None,**kwargs):
            result=original(query,params,**kwargs)
            if "SET m.state='complete'" in query:
                raise RedisConnectionError('injected acknowledgement loss')
            return result
        with tempfile.TemporaryDirectory() as d:
            bundle=evidence(d)
            importer.graph.query=lose_ack
            with self.assertRaises(ProfileError): importer.materialize(bundle)
            self.assertEqual(importer.status()['state'],'complete')
            importer.graph.query=original
            receipt=importer.materialize(bundle)
            self.assertEqual(receipt['status'],'complete')
            self.assertEqual(importer.read_projection(),load_conformant_bundle(bundle))
