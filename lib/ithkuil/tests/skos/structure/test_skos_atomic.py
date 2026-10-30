from __future__ import annotations
from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
import json
from pathlib import Path
import unittest
from rdflib.namespace import SKOS
from lib.ithkuil.src.skos.atomic import atomic_report_json_bytes, compile_atomic
from lib.ithkuil.src.skos.preflight import preflight

ROOT=ITHKUIL_ROOT; SOURCE_ROOT=ROOT/'_data'/'csv'; FIX=FIXTURES
EXPECTED=json.loads((FIX/'atomic_category_expected.json').read_text(encoding='utf-8'))

class AtomicCompilerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.c=preflight(SOURCE_ROOT).require_valid(); cls.a=compile_atomic(cls.c)
 def test_complete_current_category_accounting_matches_literal_fixture(self):
  report=self.a.as_dict(); self.assertEqual(report['source_rows'],772); self.assertEqual(report['category_count'],34)
  self.assertEqual(report['rows'],{'EMITTED':272,'HELD':500,'REJECTED':0}); self.assertEqual(report['emitted_resources'],261); self.assertEqual(report['graph_triples'],2052)
  observed={x.category_code:{'source_rows':x.source_rows,'emitted_rows':x.emitted_rows,'held_rows':x.held_rows,'rejected_rows':x.rejected_rows} for x in self.a.categories}
  self.assertEqual(observed,EXPECTED['categories'])
 def test_source_category_set_is_exactly_accounted(self):
  source={row['category_code'] for row in self.c.table('morphemes_atomic').rows}
  accounted={x.category_code for x in self.a.categories}; self.assertEqual(source,accounted); self.assertEqual(source,set(EXPECTED['categories']))
  self.assertEqual(sum(x.source_rows for x in self.a.categories),772); self.assertTrue(all(x.rejected_rows==0 for x in self.a.categories))
 def test_every_atomic_row_has_exactly_one_outcome(self):
  source=[row['atomic_id'] for row in self.c.table('morphemes_atomic').rows]; actual=[x.atomic_id for x in self.a.row_outcomes]
  self.assertEqual(len(actual),772); self.assertEqual(len(set(actual)),772); self.assertEqual(set(actual),set(source))
  self.assertEqual({x.status for x in self.a.row_outcomes},{'EMITTED','HELD'})
 def test_family_collections_do_not_invent_taxonomy(self):
  self.assertFalse(any(self.a.graph.triples((None,SKOS.broader,None)))); self.assertFalse(any(self.a.graph.triples((None,SKOS.narrower,None))))
  self.assertTrue(any(self.a.graph.triples((None,SKOS.member,None))))
 def test_current_held_reason_census_matches_literal_fixture(self):
  counts={}
  for row in self.a.row_outcomes:
   if row.status!='HELD': continue
   for reason in row.reason_codes: counts[reason]=counts.get(reason,0)+1
  self.assertEqual(counts,EXPECTED['held_reason_counts'])
 def test_report_serialization_is_deterministic(self):
  self.assertEqual(atomic_report_json_bytes(self.a),atomic_report_json_bytes(self.a)); self.assertIn(b'"category_count":34',atomic_report_json_bytes(self.a))
if __name__=='__main__': unittest.main()
