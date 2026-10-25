from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import unittest
from lib.ithkuil.src.skos.atomic import compile_atomic
from lib.ithkuil.src.skos.atomic_reconcile import atomic_reconciliation_json_bytes, reconcile_atomic
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable

ROOT=Path(__file__).resolve().parents[1]; SOURCE_ROOT=ROOT/'_data'/'csv'
def mutate(row,**changes):
 values=dict(row.values); values.update(changes); return FrozenRow(tuple((k,values[k]) for k,_ in row.values))

class AtomicReconciliationHardeningTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.c=preflight(SOURCE_ROOT).require_valid(); cls.a=compile_atomic(cls.c)
 def test_missing_row_fails_with_stable_atomic_id(self):
  target='ATOM-02a4496bfbac3a'; broken=replace(self.a,row_outcomes=tuple(r for r in self.a.row_outcomes if r.atomic_id!=target))
  with self.assertRaises(ProfileError) as caught: reconcile_atomic(self.c,broken)
  self.assertEqual(caught.exception.code,'ATOMIC_RECONCILIATION_ROW_MISMATCH'); self.assertIn(f'missing={target}',caught.exception.details)
 def test_source_census_change_changes_receipt(self):
  atom=next(r for r in self.c.table('morphemes_atomic').rows if r['atomic_id']=='ATOM-02a4496bfbac3a'); cat=next(r for r in self.c.table('grammatical_categories').rows if r['category_code']=='CONFIGURATION')
  new_atom=mutate(atom,atomic_id='ATOM-fixture-reconcile',category_code='RECONCILE_FIXTURE',value_code='FIX',value_name='fixture',semantic_summary='fixture definition',surface_form_raw='qreconcile',surface_form_normalized='qreconcile',allomorph_group_id='AG-fixture-reconcile')
  new_cat=mutate(cat,category_id='CAT-fixture-reconcile',category_code='RECONCILE_FIXTURE',category_name='Reconciliation fixture')
  tables=[]
  for t in self.c.tables:
   if t.name=='morphemes_atomic': tables.append(LoadedTable(t.name,t.columns,t.rows+(new_atom,)))
   elif t.name=='grammatical_categories': tables.append(LoadedTable(t.name,t.columns,t.rows+(new_cat,)))
   else: tables.append(t)
  c=CompilerClosure(self.c.manifest_version,tuple(tables)); changed=reconcile_atomic(c,compile_atomic(c)); baseline=reconcile_atomic(self.c,self.a)
  self.assertEqual(changed.source_row_count,773); self.assertEqual(changed.semantic_identity_count,651); self.assertNotEqual(changed.atomic_source_sha256,baseline.atomic_source_sha256); self.assertNotEqual(atomic_reconciliation_json_bytes(changed),atomic_reconciliation_json_bytes(baseline))
if __name__=='__main__': unittest.main()
