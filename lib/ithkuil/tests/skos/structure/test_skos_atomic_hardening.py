from __future__ import annotations
from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
from pathlib import Path
import unittest
from lib.ithkuil.src.skos.atomic import compile_atomic
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable

ROOT=ITHKUIL_ROOT; SOURCE_ROOT=ROOT/'_data'/'csv'
def mutate(row,**changes):
 values=dict(row.values); values.update(changes); return FrozenRow(tuple((k,values[k]) for k,_ in row.values))
def replace_atomic(closure,atomic_id,**changes):
 return CompilerClosure(closure.manifest_version,tuple(LoadedTable(t.name,t.columns,tuple(mutate(r,**changes) if t.name=='morphemes_atomic' and r['atomic_id']==atomic_id else r for r in t.rows)) if t.name=='morphemes_atomic' else t for t in closure.tables))

class AtomicCompilerHardeningTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.c=preflight(SOURCE_ROOT).require_valid()
 def test_unknown_new_category_cannot_silently_fall_through(self):
  c=replace_atomic(self.c,'ATOM-02a4496bfbac3a',category_code='FUTURE_STRUCTURAL')
  a=compile_atomic(c); row=next(x for x in a.row_outcomes if x.atomic_id=='ATOM-02a4496bfbac3a')
  self.assertEqual(row.status,'HELD'); self.assertIn('UPSTREAM_RESOLUTION_HELD',row.reason_codes); self.assertIn('FUTURE_STRUCTURAL',{x.category_code for x in a.categories})
 def test_structurally_registered_category_uses_existing_pipeline(self):
  atom=next(r for r in self.c.table('morphemes_atomic').rows if r['atomic_id']=='ATOM-02a4496bfbac3a')
  cat=next(r for r in self.c.table('grammatical_categories').rows if r['category_code']=='CONFIGURATION')
  new_atom=mutate(atom,atomic_id='ATOM-fixture-future',category_code='FUTURE_STRUCTURAL',value_code='FUT',value_name='fixture future value',semantic_summary='fixture future semantic summary',surface_form_raw='qfixture',surface_form_normalized='qfixture',allomorph_group_id='AG-fixture-future')
  new_cat=mutate(cat,category_id='CAT-fixture-future',category_code='FUTURE_STRUCTURAL',category_name='Fixture future category')
  tables=[]
  for t in self.c.tables:
   if t.name=='morphemes_atomic': tables.append(LoadedTable(t.name,t.columns,t.rows+(new_atom,)))
   elif t.name=='grammatical_categories': tables.append(LoadedTable(t.name,t.columns,t.rows+(new_cat,)))
   else: tables.append(t)
  c=CompilerClosure(self.c.manifest_version,tuple(tables)); a=compile_atomic(c)
  row=next(x for x in a.row_outcomes if x.atomic_id=='ATOM-fixture-future'); self.assertEqual(row.status,'EMITTED'); self.assertEqual(row.semantic_iri,'https://github.com/Entif-AI/Bilqis-MLX/id/grammar/FUTURE_STRUCTURAL/FUT')
 def test_reordering_preserves_complete_atomic_report(self):
  c=CompilerClosure(self.c.manifest_version,tuple(LoadedTable(t.name,t.columns,tuple(reversed(t.rows))) for t in reversed(self.c.tables)))
  baseline=compile_atomic(self.c); shuffled=compile_atomic(c); self.assertEqual(baseline.as_dict(),shuffled.as_dict()); self.assertEqual(set(baseline.graph),set(shuffled.graph))
if __name__=='__main__': unittest.main()
