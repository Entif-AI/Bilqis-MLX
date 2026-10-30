from __future__ import annotations
from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
import json
from pathlib import Path
import unittest
from lib.ithkuil.src.skos.collision import (HomographAdmission, analyze_atomic_collisions,
    collision_report_json_bytes, collision_resolution)
from lib.ithkuil.src.skos.builder import build_core_graph
from lib.ithkuil.src.skos.preflight import preflight
from lib.ithkuil.src.skos.resolver import resolve_identities
from lib.ithkuil.src.skos.source import SourceProjector

ROOT=ITHKUIL_ROOT; SOURCE_ROOT=ROOT/"_data"/"csv"; FIX=FIXTURES
EXPECTED=json.loads((FIX/"collision_expected.json").read_text(encoding="utf-8"))
ADMISSION=json.loads((FIX/"collision_admission_fixture.json").read_text(encoding="utf-8"))

class CollisionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.closure=preflight(SOURCE_ROOT).require_valid(); cls.resolution=resolve_identities(cls.closure)
  cls.report=analyze_atomic_collisions(cls.closure,cls.resolution)
 def record(self, fixture):
  return next(r for r in self.report.records if (r.key.scheme_iri,r.key.datatype_iri,r.key.lexical)==(fixture['scheme_iri'],fixture['datatype_iri'],fixture['lexical']))
 def test_current_literal_counts_and_release_block(self):
  c=EXPECTED['current_counts']; self.assertEqual(self.report.claim_count,c['claim_count'])
  self.assertEqual(len(self.report.held),c['held_collision_count']); self.assertEqual(len(self.report.admitted),0)
  self.assertEqual(len(self.report.held_resource_iris),c['held_resource_count']); self.assertEqual(len(self.report.held_source_refs),c['held_row_count'])
  self.assertFalse(self.report.release_eligible); self.assertEqual(self.report.admission_issues,())
 def test_exact_real_source_collision_records(self):
  for name in ('grammar_code_act','new_ithkuil_b'):
   fixture=EXPECTED[name]; record=self.record(fixture)
   self.assertEqual(record.disposition,'HELD'); self.assertEqual(record.reason_code,'NOTATION_COLLISION')
   self.assertEqual(list(record.resource_iris),fixture['resource_iris'])
   self.assertEqual(sorted({s.record_ref.key for s in record.sources}),sorted(fixture['source_rows']))
   self.assertTrue(all(s.source_id and s.table_id and s.source_line and s.source_url for s in record.sources))
 def test_repeated_same_resource_notation_does_not_create_duplicate_claimant(self):
  nrr='https://github.com/Entif-AI/Bilqis-MLX/id/grammar/REGISTER/NRR'
  zero=next(r for r in self.report.records if r.key.lexical=='∅' and r.key.datatype_iri.endswith('/new-ithkuil'))
  self.assertEqual(zero.resource_iris.count(nrr),1)
  self.assertEqual(sorted(s.record_ref.key for s in zero.sources if s.resource_iri==nrr),sorted(EXPECTED['register_nrr_rows']))
 def test_report_serialization_is_stable_utf8(self):
  payload=collision_report_json_bytes(self.report); self.assertEqual(payload,collision_report_json_bytes(self.report)); self.assertIn('"lexical":"∅"'.encode(),payload)
 def test_collision_resolution_holds_all_claimants_without_merge(self):
  resolved=collision_resolution(self.resolution,self.report)
  self.assertEqual(len(resolved.resources),len(self.resolution.resources)-388)
  remaining={r.identity.iri for r in resolved.resources}
  for iri in EXPECTED['grammar_code_act']['resource_iris']: self.assertNotIn(iri,remaining)
  self.assertTrue(any(i.code=='NOTATION_COLLISION' for i in resolved.issues))
 def test_exact_explicit_admission_is_visible_not_global_relaxation(self):
  a=HomographAdmission(ADMISSION['scheme_iri'],ADMISSION['datatype_iri'],ADMISSION['lexical'],tuple(ADMISSION['resource_iris']),ADMISSION['rule_id'])
  report=analyze_atomic_collisions(self.closure,self.resolution,(a,)); rec=next(r for r in report.admitted if r.key.lexical=='b' and r.key.datatype_iri==ADMISSION['datatype_iri'])
  self.assertEqual(rec.admission_rule_id,ADMISSION['rule_id']); self.assertEqual(len(report.held),150); self.assertFalse(report.release_eligible)
 def test_exact_admission_reaches_existing_builder_boundary(self):
  a=HomographAdmission(ADMISSION['scheme_iri'],ADMISSION['datatype_iri'],ADMISSION['lexical'],tuple(ADMISSION['resource_iris']),ADMISSION['rule_id'])
  selected=tuple(r for r in self.resolution.resources if r.identity.iri in set(ADMISSION['resource_iris']))
  strict=build_core_graph(selected,SourceProjector(self.closure)); self.assertEqual(strict.emitted,()); self.assertEqual({i.code for i in strict.issues},{'NOTATION_COLLISION'})
  admitted=build_core_graph(selected,SourceProjector(self.closure),notation_admissions=(a,))
  self.assertEqual({r.identity.iri for r in admitted.emitted},set(ADMISSION['resource_iris'])); self.assertNotIn('NOTATION_COLLISION',{i.code for i in admitted.issues})

if __name__=='__main__': unittest.main()
