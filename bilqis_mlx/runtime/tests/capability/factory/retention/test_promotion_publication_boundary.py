"""B09.3 production composition at the retained C05 -> B13 boundary."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import CandidateState
from bilqis_mlx.learning.atlas_candidate import issue_promotion_transition_state
from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime._plasticity_promotion import receipt as receipt_owner
from bilqis_mlx.runtime.bamf_bundle.admission import _apply_promotion_transition_if_due
from bilqis_mlx.runtime.plasticity_promotion import promotion_transition_pending
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import accepted_state, parent_state
from bilqis_mlx.runtime.tests.capability.factory.plasticity_promotion_support import FOUNDATION


@dataclass(frozen=True)
class _Bundle:
    retained_state: object
    marker: str = "preserved"


class PromotionPublicationBoundaryTests(TestCase):
    def test_no_attempt_preserves_exact_candidate_and_bundle(self):
        state = object()
        bundle = _Bundle(state)
        with patch(
                "bilqis_mlx.runtime.bamf_bundle.admission."
                "promotion_transition_pending", return_value=False):
            actual_bundle, actual_state = _apply_promotion_transition_if_due(
                object(), bundle, state, object())
        self.assertIs(actual_bundle, bundle)
        self.assertIs(actual_state, state)

    def test_due_attempt_replaces_only_retained_state_before_publication(self):
        state, transitioned, receipt, decision = object(), object(), object(), object()
        bundle = _Bundle(state)
        with (
            patch(
                "bilqis_mlx.runtime.bamf_bundle.admission."
                "promotion_transition_pending", return_value=True),
            patch(
                "bilqis_mlx.runtime.bamf_bundle.admission."
                "issue_accepted_promotion_transition", return_value=receipt),
            patch(
                "bilqis_mlx.runtime.bamf_bundle.admission."
                "issue_promotion_transition_state", return_value=transitioned),
        ):
            actual_bundle, actual_state = _apply_promotion_transition_if_due(
                object(), bundle, state, decision)
        self.assertIs(actual_state, transitioned)
        self.assertIs(actual_bundle.retained_state, transitioned)
        self.assertEqual(actual_bundle.marker, bundle.marker)
        self.assertIs(bundle.retained_state, state)

    def test_raw_live_receipt_mint_is_not_module_reachable(self):
        self.assertFalse(hasattr(receipt_owner, "_raw_issue_receipt"))

    def test_historical_attempt_for_prior_student_is_not_pending(self):
        fixture_parent = parent_state()
        parent = CandidateState(
            fixture_parent.optimizer,
            PlasticityPolicy(row_ages=fixture_parent.policy.row_ages),
            fixture_parent.allocations, fixture_parent.optimizer_step,
            fixture_parent.custody, fixture_parent.step_proofs)
        retained = accepted_state(parent)
        prior_identity = candidate_identity_digest(parent)
        school = SimpleNamespace(
            current_student=SimpleNamespace(
                sha256=prior_identity, optimizer_step=parent.optimizer_step),
            promotion_sweep_attempt_student_sha256=prior_identity,
            promotion_sweep_attempt_scope=FOUNDATION,
        )
        accepted = SimpleNamespace(
            run_id="fixture-run", generation=4, retained_state=parent,
            run_identity=SimpleNamespace(factory_release_sha256="2" * 64))
        cache = SimpleNamespace(run_id="fixture-run", generation=4)
        with (
            patch("bilqis_mlx.runtime.bamf_bundle.accepted_runtime.load_accepted_generation",
                  return_value=accepted),
            patch("bilqis_mlx.runtime.bamf_bundle.accepted_runtime.bind_accepted_execution_cache",
                  return_value=cache),
            patch("bilqis_mlx.state_dag.read_current",
                  return_value={"run_id": "fixture-run", "generation": 9}),
            patch("bilqis_mlx.runtime._plasticity_promotion.issuance._school_for_receipt",
                  return_value=school),
            patch("bilqis_mlx.runtime._plasticity_promotion.issuance._foundation_capabilities",
                  return_value=FOUNDATION),
        ):
            self.assertFalse(promotion_transition_pending(Path("."), retained))

    def test_transition_rejects_live_receipt_from_foreign_custody(self):
        parent = parent_state()
        retained = accepted_state(parent)
        custody = retained.custody
        receipt = SimpleNamespace(
            run_id="foreign-run", parent_generation=custody.generation,
            candidate_generation=custody.generation + 1,
            parent_manifest_sha256=custody.manifest_sha256,
            candidate_identity_sha256=candidate_identity_digest(retained),
            optimizer_step=retained.optimizer_step,
        )
        with (
            patch("bilqis_mlx.runtime.plasticity_promotion."
                  "require_accepted_promotion_transition", return_value=receipt),
            self.assertRaises(BilqisError),
        ):
            issue_promotion_transition_state(retained, receipt)
