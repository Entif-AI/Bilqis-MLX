import json
import os
import tempfile
import unittest
import uuid

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.falkor_import import Importer,connect
from lib.ithkuil.src.skos.falkor_reset import RESET_QUERY,plan_reset,reset_owned
from lib.ithkuil.tests.test_skos_falkor_import import evidence


@unittest.skipUnless(os.environ.get('BILQIS_FALKOR_LIVE')=='1','explicit isolated live proof only')
class ResetTests(unittest.TestCase):
    def prepare(self,d):
        name='bilqis_skos_19_75_'+uuid.uuid4().hex[:12];owner='reset-'+uuid.uuid4().hex
        print(json.dumps({'live_graph':name,'owner':owner}),flush=True)
        importer=Importer(connect(),name,owner);bundle=evidence(d);importer.materialize(bundle)
        return importer,bundle

    def snapshot(self,i):
        return (i._read('MATCH(n) RETURN properties(n),labels(n) ORDER BY n.key'),
                i._read('MATCH(a)-[e]->(b) RETURN a.key,properties(e),b.key,type(e) ORDER BY e.key'))

    def test_clean_reset_preserves_unrelated_foreign_data_and_rebuilds(self):
        with tempfile.TemporaryDirectory() as d:
            i,bundle=self.prepare(d)
            i.graph.query("CREATE (a:Foreign {key:'foreign-a',owner:'foreign'}),(b:Foreign {key:'foreign-b',owner:'foreign'}),(a)-[:Foreign {key:'foreign-edge',owner:'foreign'}]->(b)")
            before=self.snapshot(i);plan=plan_reset(i);self.assertEqual(before,self.snapshot(i))
            self.assertEqual(plan['owned_nodes'],39);self.assertEqual(plan['owned_edges'],63)
            self.assertEqual(plan['blockers'],[])
            result=reset_owned(i,plan);self.assertEqual(result['status'],'empty')
            self.assertEqual(i._read('MATCH(n:Foreign) RETURN n.key ORDER BY n.key'),[['foreign-a'],['foreign-b']])
            self.assertEqual(i._read('MATCH()-[e:Foreign]->() RETURN e.key'),[['foreign-edge']])
            self.assertEqual(i.materialize(bundle)['status'],'complete')

    def test_each_foreign_boundary_refuses_before_any_deletion(self):
        for case in ('incoming','outgoing','owned-edge-foreign-node'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as d:
                i,_=self.prepare(d)
                term=i._read('MATCH(n:RdfTerm) RETURN n.key ORDER BY n.key LIMIT 1')[0][0]
                direction='(f)-[e:Foreign]->(n)' if case=='incoming' else '(n)-[e:Foreign]->(f)'
                owner='foreign'
                if case=='owned-edge-foreign-node':direction='(n)-[e:RDF]->(f)';owner=i.owner
                i.graph.query('MATCH(n:RdfTerm {key:$key}) CREATE (f:Foreign {key:$foreign,owner:$foreign_owner}),'+direction+' SET e.key=$edge,e.owner=$owner',{'key':term,'foreign':case,'foreign_owner':'foreign','edge':'boundary-'+case,'owner':owner})
                before=self.snapshot(i);plan=plan_reset(i);self.assertTrue(plan['blockers'])
                with self.assertRaises(ProfileError):reset_owned(i,plan)
                self.assertEqual(before,self.snapshot(i))

    def test_stale_same_count_plan_and_wrong_target_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            i,_=self.prepare(d);plan=plan_reset(i)
            wrong={**plan,'graph':'another-graph'}
            with self.assertRaises(ProfileError):reset_owned(i,wrong)
            i.graph.query('MATCH(n:RdfTerm {key:$key}) SET n.key=$replacement',{'key':plan['node_keys'][0],'replacement':'same-count-swap'})
            before=self.snapshot(i)
            with self.assertRaises(ProfileError):reset_owned(i,plan)
            self.assertEqual(before,self.snapshot(i))

    def test_foreign_edge_inserted_after_final_plan_read_is_atomically_refused(self):
        with tempfile.TemporaryDirectory() as d:
            i,_=self.prepare(d);plan=plan_reset(i);original=i.graph.query
            def race(query,params=None,**kwargs):
                if query==RESET_QUERY:
                    original("MATCH(n:RdfTerm {key:$key}) CREATE (f:Foreign {key:'racer',owner:'foreign'}),(f)-[:Foreign {key:'racing-edge',owner:'foreign'}]->(n)",{'key':plan['node_keys'][0]})
                return original(query,params,**kwargs)
            i.graph.query=race
            with self.assertRaises(ProfileError):reset_owned(i,plan)
            self.assertEqual(i._read('MATCH(n:RdfTerm) RETURN count(n)'),[[39]])
            self.assertEqual(i._read('MATCH()-[e:RDF]->() RETURN count(e)'),[[63]])
            self.assertEqual(i.status()['state'],'complete')
