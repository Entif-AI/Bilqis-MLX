from pathlib import Path
import json
import unittest

from bilqis_mlx.factory.autonomy import (
    EvidenceKind, EvidenceObligation,
)
from bilqis_mlx.factory.evidence import draw_evidence_rows
from bilqis_mlx.factory.live_releases import (
    boolean_successor, compile_live_release,
)
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.source_adapters.school import live_source_registry


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

    def test_live_boolean_adapter_witnesses_exact_a_operand_slot(self):
        obligation = EvidenceObligation(
            obligation_id="B.AND/typed-composition/A.IDENTITY/slot/0",
            capability_id="B.AND",
            kind=EvidenceKind.COMPOSITION,
            key="A.IDENTITY@0",
            minimum_specimens=1,
            generation_axes=("source-valid", "fresh-seed"),
            requires_capabilities=("A.IDENTITY",),
        )
        rows = draw_evidence_rows(
            LEGACY, self.graph, self.release, self.registry,
            obligation, seed=20261019)
        self.assertEqual(len(rows), 1)
        operand = rows[0]["record"]["query"]["args"][0]
        self.assertEqual(operand["kind"], "compare")
        self.assertEqual(operand["operator"], "EQ")

    def test_live_boolean_adapter_rejects_wrong_operand_root(self):
        obligation = EvidenceObligation(
            obligation_id="B.AND/typed-composition/A.MEMBER/slot/0",
            capability_id="B.AND",
            kind=EvidenceKind.COMPOSITION,
            key="A.MEMBER@0",
            minimum_specimens=1,
            generation_axes=("source-valid", "fresh-seed"),
            requires_capabilities=("A.MEMBER",),
        )
        with self.assertRaisesRegex(ValueError, "EVIDENCE_WITNESS_EXHAUSTED"):
            draw_evidence_rows(
                LEGACY, self.graph, self.release, self.registry,
                obligation, seed=20261019, max_rounds=2)


if __name__ == "__main__":
    unittest.main()
