"""Reset enumeration must survive a provider result cap, independently of live DB."""
import unittest

from lib.ithkuil.src.skos.falkor_import import Importer
from lib.ithkuil.src.skos.falkor_reset import plan_reset


class CappedImporter(Importer):
    def __init__(self):
        self.name='paging-proof';self.owner='paging-owner';self.queries=[]
        self.nodes=[[{'key':f'n-{n:05d}'},['RdfTerm']] for n in range(10000)]
        self.nodes.insert(0,[{'owner':self.owner},['BilqisProjection']])
        self.boundaries=[[f'n-{n:05d}',self.owner,f'e-{n:05d}',self.owner,'RDF',f'n-{(n+1)%10000:05d}',self.owner] for n in range(10000)]
        self.count_delta=0

    def status(self):
        return {'version':'1.0.0','digest':'release-digest','state':'incomplete'}

    def _read(self,query,params=None):
        self.queries.append((query,params))
        rows=self.boundaries if 'MATCH(a)-[e]' in query else self.nodes
        if 'RETURN count(' in query:return [[len(rows)+self.count_delta]]
        if 'SKIP $offset LIMIT $limit' in query:
            return rows[params['offset']:params['offset']+min(params['limit'],10000)]
        return rows[:10000]


class PagingTests(unittest.TestCase):
    def test_ten_thousand_nodes_and_edges_are_complete_unique_and_stable(self):
        i=CappedImporter();plan=plan_reset(i)
        self.assertEqual(plan['blockers'],[])
        self.assertEqual(plan['owned_nodes'],10000)
        self.assertEqual(plan['owned_edges'],10000)
        self.assertEqual(len(set(plan['node_keys'])),10000)
        self.assertEqual(len(set(plan['edge_keys'])),10000)
        self.assertEqual(plan,plan_reset(i))
        self.assertEqual(plan['enumeration'],{'owned_node_rows':10001,'boundary_rows':10000})
        pages=[q for q,p in i.queries if 'SKIP' in q]
        self.assertGreater(len(pages),20)
        self.assertTrue(all('ORDER BY' in q for q in pages))
        self.assertTrue(all('count(' in q or 'SKIP' in q for q,p in i.queries))

    def test_independent_count_disagreement_blocks(self):
        i=CappedImporter();i.count_delta=1
        self.assertIn('ENUMERATION_COUNT_MISMATCH',{b['code'] for b in plan_reset(i)['blockers']})

    def test_duplicate_semantic_keys_block_even_when_row_counts_match(self):
        for rows,column in (('nodes',None),('boundaries',2)):
            with self.subTest(rows=rows):
                i=CappedImporter()
                if column is None:i.nodes[2][0]['key']=i.nodes[1][0]['key']
                else:i.boundaries[1][column]=i.boundaries[0][column]
                self.assertIn('DUPLICATE_OWNED_KEY',{b['code'] for b in plan_reset(i)['blockers']})

    def test_provider_truncation_below_page_size_blocks(self):
        i=CappedImporter();original=i._read
        def truncated(query,params=None):
            rows=original(query,params)
            return rows[:500] if 'SKIP' in query else rows
        i._read=truncated
        self.assertIn('ENUMERATION_COUNT_MISMATCH',{b['code'] for b in plan_reset(i)['blockers']})
