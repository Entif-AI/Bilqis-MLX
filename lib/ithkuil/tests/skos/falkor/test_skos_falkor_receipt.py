from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
import subprocess
import sys

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.falkor_import import Importer,connect
from lib.ithkuil.src.skos.falkor_lookup import ensure_indexes
from lib.ithkuil.src.skos.falkor_receipt import build_receipt,verify_receipt,validate_receipt
from lib.ithkuil.src.skos.falkor_smoke import SUITE_PATH
from lib.ithkuil.tests.skos.falkor.test_skos_falkor_smoke import smoke_evidence


class ReceiptSchemaTests(unittest.TestCase):
    def test_invented_complete_receipt_is_rejected(self):
        with self.assertRaises(ProfileError):validate_receipt({'status':'complete'})


@unittest.skipUnless(os.environ.get('BILQIS_FALKOR_LIVE')=='1','explicit isolated live proof only')
class ReceiptLiveTests(unittest.TestCase):
    def test_import_cli_automatically_emits_smoke_backed_materialization_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            bundle=smoke_evidence(d);name='bilqis_skos_19_78_cli_'+uuid.uuid4().hex[:10];owner='cli-'+uuid.uuid4().hex
            print(json.dumps({'live_graph':name,'owner':owner}),flush=True)
            result=subprocess.run([sys.executable,'-m','lib.ithkuil.src.skos.falkor_import','--bundle',str(bundle),'--suite',str(SUITE_PATH),'--graph',name,'--owner',owner],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            receipt=json.loads(result.stdout);validate_receipt(receipt)
            self.assertEqual(receipt['status'],'complete');self.assertTrue(receipt['smoke_suite']['passed'])

    def test_valid_receipt_and_three_independent_invalidation_cases(self):
        for case in ('canonical-mutation','graph-drift','query-failure','incomplete'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as d:
                name='bilqis_skos_19_78_'+uuid.uuid4().hex[:10];owner='receipt-'+uuid.uuid4().hex
                print(json.dumps({'live_graph':name,'owner':owner}),flush=True)
                i=Importer(connect(),name,owner);bundle=smoke_evidence(Path(d)/'bundle');i.materialize(bundle);ensure_indexes(i)
                receipt=build_receipt(i,bundle,SUITE_PATH);validate_receipt(receipt);verify_receipt(receipt,i,bundle,SUITE_PATH)
                self.assertEqual(receipt['status'],'complete');self.assertEqual(receipt['edges_by_type'],{'RDF':68})
                if case=='canonical-mutation':(bundle/'canonical.nt').write_bytes(b'')
                elif case=='graph-drift':i.graph.query("MATCH(n:RdfTerm) WHERE n.kind='literal' WITH n LIMIT 1 SET n.lexical='drift'")
                elif case=='incomplete':i.graph.query("MATCH(m:BilqisProjection) SET m.state='incomplete'")
                else:
                    suite=json.loads(SUITE_PATH.read_text());suite['queries'][0]['expected']=[['urn:incorrect']]
                    p=Path(d)/'failed-suite.json';p.write_text(json.dumps(suite))
                    with self.assertRaises(ProfileError):build_receipt(i,bundle,p)
                    with self.assertRaises(ProfileError):verify_receipt(receipt,i,bundle,p)
                    continue
                with self.assertRaises(ProfileError):verify_receipt(receipt,i,bundle,SUITE_PATH)
