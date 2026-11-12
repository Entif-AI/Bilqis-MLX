from pathlib import Path
import json
import tempfile
import unittest

from bilqis_mlx.factory.live_releases import (
    boolean_composite_successor, boolean_successor,
    compile_live_release, initial_course,
)
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.autonomy_live import LiveAutonomySession


ROOT = Path(__file__).resolve().parents[4]
LEGACY = ROOT / "vendor/legacy-v16"


class LiveAutonomySessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not LEGACY.is_dir():
            raise unittest.SkipTest("pinned finite-micro source unavailable")
        accepted = accepted_grade_a(json.loads(
            (ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text()))
        cls.a = initial_course(accepted)
        cls.b = boolean_successor(cls.a, LEGACY)
        cls.composite = boolean_composite_successor(cls.b, LEGACY)

    def test_composite_restart_preserves_provider_owned_dependency_plan(self):
        release = compile_live_release(self.composite)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            opened = LiveAutonomySession.open(root, LEGACY, release)
            supplemental = tuple(
                item for item in opened.plan.supplemental_evidence
                if item.capability_id == "B.COMPOSITE")
            self.assertEqual(
                {item.key for item in supplemental},
                {"B.NOT", "B.AND", "B.OR", "B.XOR", "B.IMPLIES", "B.IFF"},
            )
            reopened = LiveAutonomySession.open(root, LEGACY, release)
            self.assertEqual(reopened.plan, opened.plan)
            self.assertEqual(reopened.ledger, opened.ledger)

    def test_live_session_measures_and_reopens_without_optimizer(self):
        release = compile_live_release(self.a)
        _, _, graph, _, _ = read_sources(LEGACY)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            session = LiveAutonomySession.open(root, LEGACY, release)
            checkpoint = Checkpoint("e" * 64, "bundles/fixture", 0, True)
            action = session.action(checkpoint)
            self.assertEqual(action.evidence_work.capability_id, "A.IDENTITY")
            evidence = session.measure(
                graph, action.evidence_work,
                checkpoint={
                    "sha256": checkpoint.sha256,
                    "optimizer_step": checkpoint.optimizer_step,
                    "model_and_native_adamw": True,
                },
                seed=20261019,
                predictor=lambda rows: {
                    row["id"]: row["gold"] for row in rows},
            )
            self.assertTrue(evidence.passed)
            reopened = LiveAutonomySession.open(root, LEGACY, release)
            self.assertEqual(reopened.ledger, session.ledger)
            self.assertEqual(
                reopened.ledger.receipts[-1].evidence_id,
                evidence.evidence_id,
            )


if __name__ == "__main__":
    unittest.main()
