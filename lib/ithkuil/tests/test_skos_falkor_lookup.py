import json
import os
import tempfile
import unittest
import uuid

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.falkor_import import Importer,connect
from lib.ithkuil.src.skos.falkor_lookup import Reader,ensure_indexes
from lib.ithkuil.tests.test_skos_falkor_import import evidence

BASE='https://github.com/Entif-AI/Bilqis-MLX/'
A=BASE+'id/grammar/TEST/A';B=BASE+'id/grammar/TEST/B'
S=BASE+'id/sense/NI-WEB-CH02/ROOT-FIXTURE/STEM%201/BSC'

@unittest.skipUnless(os.environ.get('BILQIS_FALKOR_LIVE')=='1','explicit isolated live proof only')
class LookupTests(unittest.TestCase):
    def test_all_literal_lookup_results_with_and_without_indexes(self):
        db=connect();name='bilqis_skos_19_76_'+uuid.uuid4().hex[:12];owner='lookup-'+uuid.uuid4().hex
        print(json.dumps({'live_graph':name,'owner':owner}),flush=True)
        with tempfile.TemporaryDirectory() as d:
            i=Importer(db,name,owner);i.materialize(evidence(d));reader=Reader(i)
            before=i.read_projection()
            for indexed in (False,True,True):
                if indexed:ensure_indexes(i)
                self.assertEqual(reader.by_iri(A),[A]);self.assertEqual(reader.by_iri(A+'/missing'),[])
                self.assertEqual(reader.notation('A',BASE+'id/datatype/grammar-code'),[A])
                self.assertEqual(reader.notation('∅',BASE+'id/datatype/new-ithkuil'),[A])
                self.assertEqual(reader.notation('ẓ',BASE+'id/datatype/new-ithkuil'),[B])
                self.assertEqual(reader.notation('A',BASE+'id/datatype/new-ithkuil'),[])
                self.assertEqual(reader.label_candidates('Alpha','en'),[A])
                self.assertEqual(reader.label_candidates('alpha','en'),[])
                self.assertEqual(reader.scheme(BASE+'id/scheme/new-ithkuil'),[A,B,S])
                self.assertEqual(reader.members(BASE+'id/collection/fixture-family'),[A,B])
            self.assertEqual(i.read_projection(),before)
            plan=i.graph.explain('MATCH(n:RdfTerm) WHERE n.iri=$iri RETURN n.iri',{'iri':A})
            self.assertIn('Index',str(plan))
            print(json.dumps({'iri_query_plan':str(plan)}))
            with self.assertRaises(ProfileError):Reader(Importer(db,name,'wrong-owner'))
