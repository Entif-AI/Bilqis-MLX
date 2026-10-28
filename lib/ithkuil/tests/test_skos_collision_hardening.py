from __future__ import annotations
from pathlib import Path
import unittest
from lib.ithkuil.src.skos.collision import HomographAdmission, analyze_atomic_collisions
from lib.ithkuil.src.skos.preflight import preflight
from lib.ithkuil.src.skos.resolver import resolve_identities

ROOT=Path(__file__).resolve().parents[1]; SOURCE_ROOT=ROOT/"_data"/"csv"
class CollisionHardeningTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.c=preflight(SOURCE_ROOT).require_valid(); cls.r=resolve_identities(cls.c)
 def test_partial_claimant_admission_is_rejected(self):
  a=HomographAdmission('https://github.com/Entif-AI/Bilqis-MLX/id/scheme/new-ithkuil','https://github.com/Entif-AI/Bilqis-MLX/id/datatype/new-ithkuil','b',('https://github.com/Entif-AI/Bilqis-MLX/id/grammar/EXTENSION/ATV',),'partial')
  report=analyze_atomic_collisions(self.c,self.r,(a,)); self.assertEqual(report.admission_issues[0].code,'HOMOGRAPH_ADMISSION_MISMATCH'); self.assertEqual(len(report.held),151)
 def test_unknown_key_admission_is_rejected(self):
  a=HomographAdmission('https://github.com/Entif-AI/Bilqis-MLX/id/scheme/new-ithkuil','https://github.com/Entif-AI/Bilqis-MLX/id/datatype/new-ithkuil','definitely-not-present',('https://github.com/Entif-AI/Bilqis-MLX/id/grammar/EXTENSION/ATV',),'unknown')
  report=analyze_atomic_collisions(self.c,self.r,(a,)); self.assertEqual(report.admission_issues[0].code,'HOMOGRAPH_ADMISSION_MISMATCH')
 def test_reordered_resolution_has_identical_report(self):
  from lib.ithkuil.src.skos.resolver import Resolution
  shuffled=Resolution(tuple(reversed(self.r.resources)),tuple(reversed(self.r.issues)))
  self.assertEqual(analyze_atomic_collisions(self.c,shuffled),analyze_atomic_collisions(self.c,self.r))
if __name__=='__main__': unittest.main()
