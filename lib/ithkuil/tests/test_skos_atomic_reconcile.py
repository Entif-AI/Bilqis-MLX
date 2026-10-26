from __future__ import annotations
import json
from pathlib import Path
import unittest
from rdflib import URIRef
from rdflib.namespace import RDF, SKOS
from lib.ithkuil.src.skos.atomic import compile_atomic
from lib.ithkuil.src.skos.atomic_reconcile import atomic_reconciliation_json_bytes, reconcile_atomic
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import LoadedTable

ROOT=Path(__file__).resolve().parents[1]; SOURCE_ROOT=ROOT/'_data'/'csv'; FIX=Path(__file__).resolve().parent/'fixtures'
EXPECTED=json.loads((FIX/'atomic_reconciliation_expected.json').read_text(encoding='utf-8'))

class AtomicReconciliationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.c=preflight(SOURCE_ROOT).require_valid(); cls.compiled=compile_atomic(cls.c); cls.r=reconcile_atomic(cls.c,cls.compiled)
 def test_current_receipt_matches_literal_census_and_digests(self):
  d=self.r.as_dict(); self.assertTrue(d['conformance_complete']); self.assertEqual(d['source'],EXPECTED['source']); self.assertEqual(d['rdf'],EXPECTED['rdf']); self.assertEqual(d['held'],EXPECTED['held']); self.assertEqual(len(d['rows']),772)
 def test_identity_equation_and_emitted_traceability(self):
  self.assertEqual(self.r.semantic_identity_count,self.r.emitted_resource_count+self.r.held_identity_count); self.assertEqual(650,261+389)
  for resource in self.compiled.build.emitted:
   refs=[ref for ref in resource.source_records if ref.table=='morphemes_atomic']; self.assertTrue(refs,resource.identity.iri)
 def test_held_identities_have_no_strong_graph_assertions(self):
  held={row.semantic_iri for row in self.r.rows if row.status=='HELD'}; self.assertEqual(len(held),389)
  for iri in held:
   node=URIRef(iri); self.assertFalse(any(self.compiled.graph.triples((node,None,None)))); self.assertFalse(any(self.compiled.graph.triples((None,SKOS.member,node)))); self.assertFalse(any(self.compiled.graph.triples((None,RDF.first,node))))
 def test_reordered_source_has_identical_receipt(self):
  c=CompilerClosure(self.c.manifest_version,tuple(LoadedTable(t.name,t.columns,tuple(reversed(t.rows))) for t in reversed(self.c.tables)))
  other=reconcile_atomic(c,compile_atomic(c)); self.assertEqual(atomic_reconciliation_json_bytes(other),atomic_reconciliation_json_bytes(self.r))
 def test_json_bytes_are_stable_and_include_all_rows(self):
  payload=atomic_reconciliation_json_bytes(self.r); self.assertEqual(payload,atomic_reconciliation_json_bytes(self.r)); self.assertEqual(json.loads(payload)['rows'][0]['atomic_id'],self.r.rows[0].atomic_id)
if __name__=='__main__': unittest.main()
