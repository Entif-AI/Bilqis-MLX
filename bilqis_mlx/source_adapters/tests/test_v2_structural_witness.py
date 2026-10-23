"""Executable-v2 structural evidence keeps semantic capability authority."""
from dataclasses import replace
import json
from pathlib import Path
import unittest

from bilqis_mlx.compatibility.executable_projection import (
    compile_projected_executable_release,
)
from bilqis_mlx.factory.autonomy import EvidenceKind, obligations_for_capability
from bilqis_mlx.factory.evidence import draw_evidence_rows
from bilqis_mlx.factory.live_releases import initial_course, minimal_boolean_successor
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.runtime.autonomy_live import build_live_autonomy_plan
from bilqis_mlx.source_adapters.school import (
    live_source_registry, witness_micro_obligation,
)


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "vendor" / "legacy-v16"
MANIFEST = ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"


class V2StructuralWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        accepted = accepted_grade_a(json.loads(MANIFEST.read_text()))
        cls.grade_a = initial_course(accepted)
        historical = minimal_boolean_successor(cls.grade_a, SOURCE)
        _, _, cls.graph, _, _ = read_sources(SOURCE)
        cls.registry = live_source_registry()
        cls.release, _, cls.canonical_course = compile_projected_executable_release(
            historical, cls.grade_a, SOURCE, cls.graph)
        cls.plan = build_live_autonomy_plan(cls.release, SOURCE)
        cls.composite = obligations_for_capability(
            cls.release, "B.COMPOSITE", plan=cls.plan)

    def _obligation(self, kind, key):
        return next(
            item for item in self.composite
            if item.kind is kind and item.key == key)

    def test_v2_direct_b_has_no_a_prerequisite_and_keeps_b_composition_witness(self):
        self.assertFalse(any(
            item.kind is EvidenceKind.PREREQUISITE and item.key.startswith("A.")
            for item in self.composite))
        composition = self._obligation(EvidenceKind.COMPOSITION, "B.AND")
        composition_rows = draw_evidence_rows(
            SOURCE, self.graph, self.release, self.registry,
            composition, seed=32)
        self.assertEqual(len(composition_rows), composition.minimum_specimens)

    def test_v2_witness_fails_closed_when_producer_root_is_missing(self):
        composition = self._obligation(EvidenceKind.COMPOSITION, "B.AND")
        grade_b = self.release.curriculum.grades[1]
        producer = next(
            item for item in grade_b.capabilities
            if item.capability_id == "B.AND")
        broken_producer = replace(producer, examined_roots=())
        broken_grade = replace(
            grade_b,
            capabilities=tuple(
                broken_producer if item.capability_id == "B.AND" else item
                for item in grade_b.capabilities))
        broken_curriculum = replace(
            self.release.curriculum,
            grades=(self.release.curriculum.grades[0], broken_grade,
                    *self.release.curriculum.grades[2:]))

        row = draw_evidence_rows(
            SOURCE, self.graph, self.release, self.registry,
            composition, seed=33)[0]
        with self.assertRaisesRegex(
                ValueError, "FACTORY_MICRO_EVIDENCE_PRODUCER_ROOT_UNRESOLVED"):
            witness_micro_obligation(
                row, composition, source_root=SOURCE, graph=self.graph,
                course=broken_curriculum)


if __name__ == "__main__":
    unittest.main()
