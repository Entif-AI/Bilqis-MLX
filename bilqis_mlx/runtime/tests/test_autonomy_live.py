from pathlib import Path
import json
import tempfile
import unittest

from bilqis_mlx.factory.autonomy import (
    EvidenceKind, EvidenceReceipt, obligations_for_capability,
    record_evidence,
)
from bilqis_mlx.factory.live_releases import (
    boolean_composite_successor, boolean_identification_successor,
    boolean_successor, compile_live_release, initial_course, numeric_successor,
)
from bilqis_mlx.live_grade_c import REGISTRY_COUNTING_TARGET
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.runtime.autonomy_live import (
    advance_if_scheduled_evidence_complete, build_live_autonomy_plan,
    LiveAutonomySession, reconcile_live_autonomy_state,
    scheduled_teaching_matches,
)
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.learning.champions import Checkpoint


ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / "vendor/legacy-v16"


class LiveAutonomyBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not LEGACY.is_dir():
            raise unittest.SkipTest("pinned finite-micro source unavailable")
        accepted = accepted_grade_a(json.loads(
            (ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text()))
        cls.a = initial_course(accepted)
        cls.b = boolean_successor(cls.a, LEGACY)
        cls.composite = boolean_composite_successor(cls.b, LEGACY)
        cls.identified = boolean_identification_successor(cls.composite, LEGACY)
        cls.numeric, _ = numeric_successor(
            cls.identified, maximum=REGISTRY_COUNTING_TARGET)

    def test_live_boolean_releases_compile_without_blocking_source_debt(self):
        for course in (
                self.a, self.b, self.composite, self.identified, self.numeric):
            release = compile_live_release(course)
            plan = build_live_autonomy_plan(release, LEGACY)
            self.assertEqual(plan.coverage_debt, ())

    def test_composite_and_identification_dependencies_survive_live_plan(self):
        release = compile_live_release(self.identified)
        plan = build_live_autonomy_plan(release, LEGACY)
        composite = obligations_for_capability(
            release, "B.COMPOSITE", plan=plan)
        self.assertEqual(
            {item.key for item in composite if item.kind is EvidenceKind.COMPOSITION
             and "@" not in item.key},
            {"B.NOT", "B.AND", "B.OR", "B.XOR", "B.IMPLIES", "B.IFF"},
        )
        identification = obligations_for_capability(
            release, "B.IDBOOLOPS", plan=plan)
        self.assertTrue(
            {"B.NOT", "B.AND", "B.OR", "B.XOR", "B.IMPLIES", "B.IFF"}
            <= {item.key for item in identification
                if item.kind is EvidenceKind.PREREQUISITE})

    def test_release_change_starts_new_durable_evidence_epoch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release_b = compile_live_release(self.b)
            plan_b = build_live_autonomy_plan(release_b, LEGACY)
            ledger_b = reconcile_live_autonomy_state(root, release_b, plan_b)
            release_next = compile_live_release(self.composite)
            plan_next = build_live_autonomy_plan(release_next, LEGACY)
            ledger_next = reconcile_live_autonomy_state(
                root, release_next, plan_next)
            self.assertNotEqual(
                ledger_b.factory_release_sha256,
                ledger_next.factory_release_sha256,
            )
            self.assertEqual(ledger_next.receipts, ())

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

    def test_scheduler_alignment_never_jumps_queue(self):
        release = compile_live_release(self.a)
        plan = build_live_autonomy_plan(release, LEGACY)
        school = start_new(
            self.a, Checkpoint("e" * 64, "bundles/fixture", 0, True))
        self.assertTrue(scheduled_teaching_matches(school, "A.IDENTITY"))
        self.assertFalse(scheduled_teaching_matches(school, "A.PARENT"))
        ledger = reconcile_live_autonomy_state(
            Path(tempfile.mkdtemp()), release, plan)
        self.assertEqual(
            advance_if_scheduled_evidence_complete(
                release, plan, ledger, school, "A.PARENT"),
            school,
        )

    def test_complete_evidence_advances_only_the_current_scheduled_visit(self):
        release = compile_live_release(self.a)
        plan = build_live_autonomy_plan(release, LEGACY)
        school = start_new(
            self.a, Checkpoint("e" * 64, "bundles/fixture", 0, True))
        ledger = reconcile_live_autonomy_state(
            Path(tempfile.mkdtemp()), release, plan)
        obligation = obligations_for_capability(
            release, "A.IDENTITY", plan=plan)[0]
        ledger = record_evidence(
            release, ledger,
            EvidenceReceipt(
                obligation_id=obligation.obligation_id,
                evidence_id="live-scheduler-proof",
                checkpoint_sha256="e" * 64,
                optimizer_step=0,
                cohort_sha256="f" * 64,
                specimen_count=obligation.minimum_specimens,
                passed=True,
            ),
            plan=plan,
        )
        advanced = advance_if_scheduled_evidence_complete(
            release, plan, ledger, school, "A.IDENTITY")
        self.assertEqual(advanced.queue[0], "A.PARENT")
        self.assertEqual(advanced.visits, school.visits + 1)

    def test_live_session_measures_and_reopens_durable_evidence_without_optimizer(self):
        release = compile_live_release(self.a)
        _, _, graph, _, _ = read_sources(LEGACY)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            session = LiveAutonomySession.open(root, LEGACY, release)
            action = session.action()
            self.assertEqual(action.evidence_work.capability_id, "A.IDENTITY")
            evidence = session.measure(
                graph, action.evidence_work,
                checkpoint={
                    "sha256": "e" * 64,
                    "optimizer_step": 0,
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
