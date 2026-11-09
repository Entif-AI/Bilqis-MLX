"""C05 current-generation promotion authority for B09.3."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import tempfile
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx import state_dag
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import (
    CandidateCustodyIdentity, CandidateState, issue_promotion_transition_state,
)
from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy
from bilqis_mlx.generated_assessment import PROMOTION_ATTEMPT_LIFECYCLE
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.runtime.plasticity_promotion import (
    AcceptedPromotionTransitionReceipt,
    ParsedPromotionTransitionReceipt,
    issue_accepted_promotion_transition,
    promotion_transition_pending,
    require_accepted_promotion_transition,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state, parent_state, retention_decision,
)
from bilqis_mlx.runtime.tests.capability.factory.plasticity_promotion_support import (
    FOUNDATION, INITIAL_RELEASE, PARENT_MANIFEST, RUNTIME_RELEASE,
    ordinary_schools as _ordinary_schools, school as _school,
)

class PlasticityPromotionAuthorityTests(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="b09-466-promotion-")
        self.run_dir = Path(self.temporary.name)
        fixture_parent = parent_state()
        self.parent_state = CandidateState(
            fixture_parent.optimizer,
            PlasticityPolicy(row_ages=fixture_parent.policy.row_ages),
            fixture_parent.allocations,
            fixture_parent.optimizer_step,
            fixture_parent.custody,
            fixture_parent.step_proofs,
        )
        retained = accepted_state(self.parent_state)
        self.retained = CandidateState(
            retained.optimizer, retained.policy, retained.allocations,
            retained.optimizer_step,
            CandidateCustodyIdentity(
                "fixture-run", 4, PARENT_MANIFEST,
                retained.custody.topology_digest, retained.custody.extents_digest),
            retained.step_proofs,
        )
        self.parent_identity = candidate_identity_digest(self.parent_state)
        self.candidate_identity = candidate_identity_digest(self.retained)
        self.decision = retention_decision(
            parent=self.parent_state, retained=self.retained)
        self.parent = SimpleNamespace(
            run_id="fixture-run",
            generation=4,
            retained_state=self.parent_state,
            run_identity=SimpleNamespace(
                factory_release_sha256=INITIAL_RELEASE),
        )
        self.cache = SimpleNamespace(
            run_id="fixture-run",
            generation=4,
            accepted_manifest_sha256=PARENT_MANIFEST,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def _persist(self, schools, *, final_score=9):
        for generation in range(5):
            receipt = {
                "run_id": "fixture-run",
                "generation": generation,
                "factory_release_sha256": RUNTIME_RELEASE,
                "school": {"fixture_generation": generation},
            }
            if generation == 4:
                receipt["last_exam"] = {
                    "student_sha256": self.candidate_identity,
                    "optimizer_step": self.retained.optimizer_step,
                    "grade_test_lifecycle": PROMOTION_ATTEMPT_LIFECYCLE,
                    "assessment_scope_sha256": _fingerprint(FOUNDATION),
                    "scores": {
                        "A.TWO": {"correct": final_score, "total": 10},
                    },
                }
            state_dag.persist(self.run_dir, receipt)
        return schools

    def _issue(self, schools, *, cache=None):
        self._persist(schools)
        with (
            patch(
                "bilqis_mlx.runtime.bamf_bundle.accepted_runtime."
                "load_accepted_generation",
                return_value=self.parent,
            ),
            patch(
                "bilqis_mlx.runtime.bamf_bundle.accepted_runtime."
                "bind_accepted_execution_cache",
                return_value=self.cache if cache is None else cache,
            ),
            patch(
                "bilqis_mlx.runtime._plasticity_promotion.issuance."
                "_foundation_capabilities",
                return_value=FOUNDATION,
            ),
            patch(
                "bilqis_mlx.runtime._plasticity_promotion.issuance._school_for_receipt",
                side_effect=lambda _root, receipt: schools[receipt["generation"]],
            ),
            patch(
                "bilqis_mlx.runtime._plasticity_promotion.evidence._school_for_receipt",
                side_effect=lambda _root, receipt: schools[receipt["generation"]],
            ),
        ):
            self.assertTrue(promotion_transition_pending(self.run_dir, self.retained))
            return issue_accepted_promotion_transition(
                self.run_dir, self.retained, self.decision)

    def test_live_current_generation_receipt_uses_immutable_state_dag(self):
        receipt = self._issue(
            _ordinary_schools(
                self.candidate_identity, self.retained.optimizer_step))
        self.assertIs(
            require_accepted_promotion_transition(receipt), receipt)
        self.assertEqual(receipt.run_id, "fixture-run")
        self.assertEqual(receipt.parent_generation, 4)
        self.assertEqual(receipt.candidate_generation, 5)
        self.assertEqual(
            receipt.parent_candidate_identity_sha256, self.parent_identity)
        self.assertEqual(
            receipt.candidate_identity_sha256, self.candidate_identity)
        self.assertEqual(receipt.foundation_capability_ids, FOUNDATION)
        self.assertEqual(receipt.promotion_state_generations, (0, 1, 2, 3, 4))
        self.assertEqual(receipt.outcome, "PROMOTED")
        self.assertEqual(receipt.carried_debt, ())
        parsed = AcceptedPromotionTransitionReceipt.from_record(
            receipt.to_record())
        self.assertIsInstance(parsed, ParsedPromotionTransitionReceipt)
        self.assertEqual(parsed.digest, receipt.digest)
        with self.assertRaises(BilqisError):
            require_accepted_promotion_transition(parsed)
        transitioned = issue_promotion_transition_state(self.retained, receipt)
        self.assertIs(transitioned.optimizer, self.retained.optimizer)
        self.assertIs(transitioned.allocations, self.retained.allocations)
        self.assertEqual(transitioned.optimizer_step, self.retained.optimizer_step)
        self.assertEqual(transitioned.custody, self.retained.custody)
        self.assertEqual(transitioned.step_proofs, self.retained.step_proofs)
        self.assertEqual(transitioned.policy.mode, "ADAPTIVE")
        self.assertEqual(transitioned.policy.mode_transition.promotion_receipt_sha256,
                         receipt.digest)

    def test_debt_boundary_is_preserved_without_perfect_claim(self):
        schools = _ordinary_schools(
            self.candidate_identity, self.retained.optimizer_step)
        schools[4] = _school(
            self.candidate_identity, self.retained.optimizer_step,
            stage="MAIN", queue=("B.ONE",), epoch=0, grade_index=1,
            debt=("A.TWO",))
        receipt = self._issue(schools)
        self.assertEqual(receipt.outcome, "PROMOTED_WITH_DEBT")
        self.assertEqual(receipt.carried_debt, ("A.TWO",))

    def test_thresholds_incomplete_sweep_and_stale_b13_fail_closed(self):
        below_entry = _ordinary_schools(
            self.candidate_identity, self.retained.optimizer_step,
            entry_score=9)
        with self.assertRaises(BilqisError):
            self._issue(below_entry)

        self.temporary.cleanup()
        self.temporary = tempfile.TemporaryDirectory(prefix="b09-466-promotion-")
        self.run_dir = Path(self.temporary.name)
        below_continuation = _ordinary_schools(
            self.candidate_identity, self.retained.optimizer_step,
            continuation_score=7)
        with self.assertRaises(BilqisError):
            self._issue(below_continuation)

        self.temporary.cleanup()
        self.temporary = tempfile.TemporaryDirectory(prefix="b09-466-promotion-")
        self.run_dir = Path(self.temporary.name)
        incomplete = _ordinary_schools(
            self.candidate_identity, self.retained.optimizer_step)
        incomplete[3] = _school(
            self.candidate_identity, self.retained.optimizer_step,
            stage="PROMOTION_SWEEP", queue=(), scores=incomplete[3].promotion_sweep_scores)
        with self.assertRaises(BilqisError):
            self._issue(incomplete)

        self.temporary.cleanup()
        self.temporary = tempfile.TemporaryDirectory(prefix="b09-466-promotion-")
        self.run_dir = Path(self.temporary.name)
        reordered = _ordinary_schools(
            self.candidate_identity, self.retained.optimizer_step)
        reordered[2] = _school(
            self.candidate_identity, self.retained.optimizer_step,
            stage="ASSESS_PROMOTION_SWEEP", queue=("A.TWO",),
            scores=reordered[2].promotion_sweep_scores)
        with self.assertRaises(BilqisError):
            self._issue(reordered)

        self.temporary.cleanup()
        self.temporary = tempfile.TemporaryDirectory(prefix="b09-466-promotion-")
        self.run_dir = Path(self.temporary.name)
        stale = SimpleNamespace(
            run_id="fixture-run", generation=3,
            accepted_manifest_sha256=PARENT_MANIFEST)
        with self.assertRaises(BilqisError):
            self._issue(_ordinary_schools(
                self.candidate_identity, self.retained.optimizer_step), cache=stale)

    def test_callers_cannot_construct_live_receipts(self):
        values = {
            "run_id": "fixture-run",
            "parent_generation": 4,
            "candidate_generation": 5,
            "parent_manifest_sha256": PARENT_MANIFEST,
            "parent_candidate_identity_sha256": self.parent_identity,
            "candidate_identity_sha256": self.candidate_identity,
            "optimizer_step": self.retained.optimizer_step,
            "decision_sha256": self.decision.digest,
            "initial_factory_release_sha256": INITIAL_RELEASE,
            "foundation_capability_ids": FOUNDATION,
            "promotion_state_generations": (0, 1, 2, 3, 4),
            "promotion_evidence_sha256": "4" * 64,
            "assessment_epoch": 1,
            "outcome": "PROMOTED",
            "carried_debt": (),
        }
        with self.assertRaises(BilqisError):
            AcceptedPromotionTransitionReceipt(**values)
