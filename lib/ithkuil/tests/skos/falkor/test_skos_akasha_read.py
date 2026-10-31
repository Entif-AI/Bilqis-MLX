from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
import json
import os
from pathlib import Path
import secrets
import tempfile
import unittest
import uuid

from falkordb import FalkorDB
import redis
from redis.exceptions import NoPermissionError

from lib.ithkuil.src.skos.akasha_skos import AkashaSkosClient
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.falkor_import import Importer,connect
from lib.ithkuil.src.skos.falkor_receipt import build_receipt
from lib.ithkuil.src.skos.falkor_smoke import SUITE_PATH
from lib.ithkuil.tests.skos.falkor.test_skos_falkor_smoke import smoke_evidence
from lib.ithkuil.tests.skos.conformance.test_skos_shacl import BASE

A=BASE+'id/grammar/TEST/A';B=BASE+'id/grammar/TEST/B'


@unittest.skipUnless(os.environ.get('BILQIS_FALKOR_LIVE')=='1','explicit isolated live proof only')
class AkashaReadTests(unittest.TestCase):
    def prepare(self,d):
        name='bilqis_skos_19_79_'+uuid.uuid4().hex[:10];owner='akasha-'+uuid.uuid4().hex
        print(json.dumps({'live_graph':name,'owner':owner}),flush=True)
        bundle=smoke_evidence(d);i=Importer(connect(),name,owner);i.materialize(bundle)
        receipt=build_receipt(i,bundle,SUITE_PATH)
        return i,bundle,receipt

    def test_read_only_credential_executes_literal_journey_without_semantic_writes(self):
        with tempfile.TemporaryDirectory() as d:
            i,bundle,receipt=self.prepare(d);before=i.read_projection()
            admin=redis.Redis(host='127.0.0.1',port=16379,username=os.environ.get('BILQIS_FALKOR_USERNAME'),password=os.environ.get('BILQIS_FALKOR_PASSWORD'))
            user='bilqis_skos_read_'+uuid.uuid4().hex;secret=secrets.token_urlsafe(32)
            try:
                admin.acl_setuser(user,enabled=True,passwords=['+'+secret],keys=[i.name],commands=['+ping','+info','+graph.ro_query','+graph.list','+client|setinfo'])
                db=FalkorDB(host='127.0.0.1',port=16379,username=user,password=secret,socket_timeout=15)
                client=AkashaSkosClient(db,i.name,i.owner,receipt,bundle,SUITE_PATH)
                result=client.read('∅',BASE+'id/datatype/new-ithkuil',expected_iri=A)
                self.assertEqual(result['concept_iri'],A)
                self.assertEqual(result['families'],[BASE+'id/collection/fixture-family'])
                self.assertEqual(result['schemes'],[BASE+'id/scheme/fixture-secondary'])
                self.assertEqual(result['neighbors'],[
                    {'predicate_iri':'http://www.w3.org/2004/02/skos/core#closeMatch','target_iri':B},
                    {'predicate_iri':'http://www.w3.org/2004/02/skos/core#related','target_iri':B}])
                self.assertEqual(result['canonical_rdf_sha256'],'f1861614be87247978c4ac44eae646de9c0e110a046c0afde3234f238ecce015')
                with self.assertRaises(NoPermissionError):db.select_graph(i.name).query('CREATE(n:ForbiddenWrite)')
                with self.assertRaises(NoPermissionError):db.select_graph(i.name+'_unrelated').ro_query('RETURN 1')
            finally:admin.acl_deluser(user)
            self.assertEqual(i.read_projection(),before)

    def test_missing_stale_digest_ambiguous_and_missing_concept_fail_explicitly(self):
        with tempfile.TemporaryDirectory() as d:
            i,bundle,receipt=self.prepare(d);db=connect()
            with self.assertRaises(ProfileError):AkashaSkosClient(db,i.name+'_absent',i.owner,receipt,bundle,SUITE_PATH)
            for changed in ({**receipt,'status':'incomplete','reason':'test'}, {**receipt,'canonical_rdf_sha256':'0'*64}):
                with self.assertRaises(ProfileError):AkashaSkosClient(db,i.name,i.owner,changed,bundle,SUITE_PATH).read('∅',BASE+'id/datatype/new-ithkuil',expected_iri=A)
            client=AkashaSkosClient(db,i.name,i.owner,receipt,bundle,SUITE_PATH)
            with self.assertRaises(ProfileError):client.read('absent',BASE+'id/datatype/new-ithkuil',expected_iri=A)
            with self.assertRaises(ProfileError):client.read('-Č-',BASE+'id/datatype/new-ithkuil',expected_iri=BASE+'id/root/NI-WEB-CH02/ROOT-FIXTURE')
            i.graph.query('CREATE(:BilqisProjection {owner:$owner})',{'owner':i.owner})
            with self.assertRaises(ProfileError):AkashaSkosClient(db,i.name,i.owner,receipt,bundle,SUITE_PATH)
