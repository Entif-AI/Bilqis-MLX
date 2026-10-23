from pathlib import Path
import json
import unittest

from bilqis_mlx.factory.autonomy import (
    EvidenceKind, EvidenceObligation, obligations_for_capability,
)
from bilqis_mlx.factory.evidence import draw_evidence_rows
from bilqis_mlx.factory.live_releases import (
    boolean_composite_successor, boolean_identification_successor,
    boolean_successor, compile_live_release, numeric_successor,
)
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.live_grade_c import REGISTRY_COUNTING_TARGET, registry_graph
from bilqis_mlx.runtime.autonomy_live import build_live_autonomy_plan


ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / "vendor" / "legacy-v16"


class LiveMicroAutonomyEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not LEGACY.is_dir():
            raise unittest.SkipTest("pinned finite-micro source unavailable")
        grade_a = accepted_grade_a(json.loads(
            (ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text()))
        cls.course = boolean_successor(grade_a, LEGACY)
        cls.release = compile_live_release(cls.course)
        _, _, cls.graph, _, _ = read_sources(LEGACY)
        cls.registry = live_source_registry()

    def test_live_boolean_adapter_has_no_a_operand_obligations(self):
        plan = build_live_autonomy_plan(self.release, LEGACY)
        obligations = obligations_for_capability(
            self.release, "B.AND", plan=plan)
        self.assertFalse(any(
            required.startswith("A.")
            for obligation in obligations
            for required in obligation.requires_capabilities))

    def test_live_boolean_capability_declares_no_a_prerequisite(self):
        self.assertEqual(self.course.capability_map["B.AND"].prerequisites, ())

    def test_numeric_adapter_witnesses_declared_prerequisite_transfer(self):
        composite = boolean_composite_successor(self.course, LEGACY)
        identified = boolean_identification_successor(composite, LEGACY)
        numeric, _ = numeric_successor(
            identified, maximum=REGISTRY_COUNTING_TARGET)
        release = compile_live_release(numeric)
        obligation = EvidenceObligation(
            obligation_id="C.ADD/prerequisite/C.SUCCESSOR",
            capability_id="C.ADD",
            kind=EvidenceKind.PREREQUISITE,
            key="C.SUCCESSOR",
            minimum_specimens=1,
            generation_axes=("source-valid", "fresh-seed"),
            requires_capabilities=("C.SUCCESSOR",),
        )
        rows = draw_evidence_rows(
            LEGACY, registry_graph(), release, self.registry,
            obligation, seed=20261019)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["capability"], "C.ADD")
        self.assertEqual(rows[0]["lesson_id"], "LESSON-060")


if __name__ == "__main__":
    unittest.main()
