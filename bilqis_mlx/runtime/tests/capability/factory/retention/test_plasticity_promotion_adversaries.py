"""Fresh-Goldfish adversaries for B09.3 live C05 promotion issuance."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx import state_dag
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.generated_assessment import PROMOTION_ATTEMPT_LIFECYCLE
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import CandidateCustodyIdentity, CandidateState
from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy
from bilqis_mlx.runtime.plasticity_promotion import issue_accepted_promotion_transition
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.runtime.tests.capability.factory.plasticity_promotion_support import (
    FOUNDATION, INITIAL_RELEASE, PARENT_MANIFEST, RUNTIME_RELEASE,
    ordinary_schools, school,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state, parent_state, retention_decision,
)


class PlasticityPromotionAdversaries(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="b09-466-adversary-")
        self.run_dir = Path(self.temporary.name)
        fixture_parent = parent_state()
        self.parent_state = CandidateState(
            fixture_parent.optimizer,
            PlasticityPolicy(row_ages=fixture_parent.policy.row_ages),
            fixture_parent.allocations, fixture_parent.optimizer_step,
            fixture_parent.custody, fixture_parent.step_proofs)
        retained = accepted_state(self.parent_state)
        self.retained = CandidateState(
            retained.optimizer, retained.policy, retained.allocations,
            retained.optimizer_step,
            CandidateCustodyIdentity(
                "fixture-run", 4, PARENT_MANIFEST,
                retained.custody.topology_digest, retained.custody.extents_digest),
            retained.step_proofs)
        self.candidate_identity = candidate_identity_digest(self.retained)
        self.decision = retention_decision(
            parent=self.parent_state, retained=self.retained)
        self.parent = SimpleNamespace(
            run_id="fixture-run", generation=4, retained_state=self.parent_state,
            run_identity=SimpleNamespace(factory_release_sha256=INITIAL_RELEASE))
        self.cache = SimpleNamespace(
            run_id="fixture-run", generation=4,
            accepted_manifest_sha256=PARENT_MANIFEST)

    def tearDown(self):
        self.temporary.cleanup()

    def _persist(self, *, release_drift_generation=None, scope=None):
        for generation in range(5):
            receipt = {
                "run_id": "fixture-run", "generation": generation,
                "factory_release_sha256": (
                    "9" * 64 if generation == release_drift_generation else RUNTIME_RELEASE),
                "school": {"fixture_generation": generation},
            }
            if generation == 4:
                receipt["last_exam"] = {
                    "student_sha256": self.candidate_identity,
                    "optimizer_step": self.retained.optimizer_step,
                    "grade_test_lifecycle": PROMOTION_ATTEMPT_LIFECYCLE,
                    "assessment_scope_sha256": _fingerprint(
                        FOUNDATION if scope is None else scope),
                    "scores": {"A.TWO": {"correct": 9, "total": 10}},
                }
            state_dag.persist(self.run_dir, receipt)

    def _issue(self, schools, *, release_drift_generation=None, scope=None):
        self._persist(
            release_drift_generation=release_drift_generation, scope=scope)
        with (
            patch(
                "bilqis_mlx.runtime.bamf_bundle.accepted_runtime."
                "load_accepted_generation", return_value=self.parent),
            patch(
                "bilqis_mlx.runtime.bamf_bundle.accepted_runtime."
                "bind_accepted_execution_cache", return_value=self.cache),
            patch(
                "bilqis_mlx.runtime._plasticity_promotion.issuance."
                "_foundation_capabilities", return_value=FOUNDATION),
            patch(
                "bilqis_mlx.runtime._plasticity_promotion.issuance."
                "_school_for_receipt",
                side_effect=lambda _root, receipt: schools[receipt["generation"]]),
            patch(
                "bilqis_mlx.runtime._plasticity_promotion.evidence."
                "_school_for_receipt",
                side_effect=lambda _root, receipt: schools[receipt["generation"]]),
        ):
            return issue_accepted_promotion_transition(
                self.run_dir, self.retained, self.decision)

    def test_grade_index_permutation_does_not_change_promotion_authority(self):
        baseline = self._issue(
            ordinary_schools(self.candidate_identity, self.retained.optimizer_step))
        self.temporary.cleanup()
        self.temporary = tempfile.TemporaryDirectory(prefix="b09-466-adversary-")
        self.run_dir = Path(self.temporary.name)
        permuted = ordinary_schools(self.candidate_identity, self.retained.optimizer_step)
        for generation, value in tuple(permuted.items()):
            permuted[generation] = SimpleNamespace(
                **{**vars(value), "grade_index": value.grade_index + 7})
        actual = self._issue(permuted)
        self.assertEqual(actual.to_record(), baseline.to_record())

    def test_substituted_current_student_is_rejected(self):
        schools = ordinary_schools(self.candidate_identity, self.retained.optimizer_step)
        schools[4] = school(
            "f" * 64, self.retained.optimizer_step,
            stage="MAIN", queue=("B.ONE",), epoch=1, grade_index=1)
        with self.assertRaises(BilqisError):
            self._issue(schools)

    def test_state_dag_exam_scope_tamper_is_rejected(self):
        with self.assertRaises(BilqisError):
            self._issue(
                ordinary_schools(self.candidate_identity, self.retained.optimizer_step),
                scope=("A.ONE",))

    def test_mid_sweep_factory_release_drift_is_rejected(self):
        with self.assertRaises(BilqisError):
            self._issue(
                ordinary_schools(self.candidate_identity, self.retained.optimizer_step),
                release_drift_generation=2)
