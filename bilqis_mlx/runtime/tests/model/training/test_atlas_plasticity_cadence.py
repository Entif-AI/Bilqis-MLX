"""B09 cadence and accepted promotion-transition behavior."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge

class PlasticityCadenceTests(TestCase):
    @staticmethod
    def _promotion_receipt(**changes):
        values = {
            "run_id": "run-466",
            "parent_generation": 4,
            "candidate_generation": 5,
            "candidate_identity_sha256": "a" * 64,
            "optimizer_step": 12,
            "decision_sha256": "b" * 64,
            "initial_factory_release_sha256": "c" * 64,
            "foundation_capability_ids": ("A.ONE", "A.TWO"),
            "promotion_evidence_sha256": "d" * 64,
            "assessment_epoch": 7,
            "outcome": "PROMOTED",
            "carried_debt": (),
            "digest": "e" * 64,
        }
        values.update(changes)
        return SimpleNamespace(**values)

    def test_foundation_and_rejection_preserve_cadence(self):
        from bilqis_mlx.learning.atlas_plasticity import (
            PlasticityPolicy, next_update_mode, advance_candidate_policy,
        )
        parent = PlasticityPolicy(row_ages=(IdentityRowAge(0, 1, 0),))
        self.assertEqual(next_update_mode(parent, teacher_requests_full=False), "FULL")
        self.assertIs(advance_candidate_policy(parent, teacher_requests_full=False,
                      accepted=False, participating_rows=((0, 1),)), parent)
        actual = advance_candidate_policy(parent, teacher_requests_full=False,
                     accepted=True, participating_rows=((0, 1),))
        self.assertEqual(actual.mode, "FOUNDATION")
        self.assertEqual(actual.accepted_fast_since_full, 0)
        self.assertEqual(actual.row_ages[0].accepted_age, 1)
        self.assertEqual(parent.row_ages[0].accepted_age, 0)

    def test_eight_accepted_fast_then_full_across_cold_readback(self):
        import json
        from bilqis_mlx.learning.atlas_plasticity import (
            PlasticityPolicy, next_update_mode, advance_candidate_policy,
        )
        state = PlasticityPolicy(mode="ADAPTIVE", row_ages=(IdentityRowAge(0, 1, 0),))
        for count in range(8):
            self.assertEqual(next_update_mode(state, teacher_requests_full=False), "FAST")
            self.assertIs(advance_candidate_policy(state, teacher_requests_full=False,
                          accepted=False, participating_rows=((0, 1),)), state)
            state = advance_candidate_policy(state, teacher_requests_full=False,
                        accepted=True, participating_rows=((0, 1),))
            state = PlasticityPolicy.from_record(json.loads(json.dumps(state.to_record())))
            self.assertEqual(state.accepted_fast_since_full, count + 1)
            self.assertEqual(state.row_ages[0].accepted_age, count + 1)
        self.assertEqual(next_update_mode(state, teacher_requests_full=False), "FULL")
        self.assertIs(advance_candidate_policy(state, teacher_requests_full=False,
                      accepted=False, participating_rows=()), state)
        state = advance_candidate_policy(state, teacher_requests_full=False,
                    accepted=True, participating_rows=((0, 1),))
        self.assertEqual(state.accepted_fast_since_full, 0)
        self.assertEqual(state.row_ages[0].accepted_age, 8)
        self.assertEqual(next_update_mode(state, teacher_requests_full=False), "FAST")

    def test_teacher_full_and_idle_rows(self):
        from bilqis_mlx.learning.atlas_plasticity import (
            PlasticityPolicy, next_update_mode, advance_candidate_policy,
        )
        parent = PlasticityPolicy(mode="ADAPTIVE", accepted_fast_since_full=3,
                                  row_ages=(IdentityRowAge(0, 1, 7), IdentityRowAge(0, 2, 0)))
        self.assertEqual(next_update_mode(parent, teacher_requests_full=True), "FULL")
        self.assertIs(advance_candidate_policy(parent, teacher_requests_full=True,
                      accepted=False, participating_rows=((0, 1),)), parent)
        actual = advance_candidate_policy(parent, teacher_requests_full=True,
                     accepted=True, participating_rows=((0, 1),))
        self.assertEqual(actual.accepted_fast_since_full, 0)
        self.assertEqual(tuple(row.accepted_age for row in actual.row_ages), (8, 0))
        self.assertEqual(actual.mode, "ADAPTIVE")

    def test_policy_records_fail_closed_without_inferred_defaults(self):
        from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy, next_update_mode
        valid = PlasticityPolicy().to_record()
        for key in valid:
            changed = dict(valid)
            del changed[key]
            with self.assertRaises(BilqisError):
                PlasticityPolicy.from_record(changed)
        for patch in ({"mode": "FAST"}, {"accepted_fast_since_full": True},
                      {"accepted_fast_since_full": -1}, {"policy_version": "other"},
                      {"extra": 1}, {"row_ages": [{"bank_index": 0}]}):
            with self.assertRaises(BilqisError):
                PlasticityPolicy.from_record(dict(valid, **patch))
        with self.assertRaises(BilqisError):
            PlasticityPolicy(accepted_fast_since_full=1)
        with self.assertRaises(BilqisError):
            next_update_mode(PlasticityPolicy(), teacher_requests_full=1)

    def test_overdue_counter_uses_literal_greater_equal_contract(self):
        from bilqis_mlx.learning.atlas_plasticity import (
            PlasticityPolicy, next_update_mode, advance_candidate_policy,
        )
        parent = PlasticityPolicy.from_record(
            PlasticityPolicy(mode="ADAPTIVE", accepted_fast_since_full=9).to_record())
        self.assertEqual(next_update_mode(parent, teacher_requests_full=False), "FULL")
        self.assertIs(advance_candidate_policy(parent, teacher_requests_full=False,
                      accepted=False, participating_rows=()), parent)
        actual = advance_candidate_policy(parent, teacher_requests_full=False,
                     accepted=True, participating_rows=())
        self.assertEqual(actual.accepted_fast_since_full, 0)

    def test_live_promotion_receipt_transitions_once_and_round_trips_v2(self):
        import json
        from bilqis_mlx.learning.atlas_plasticity import (
            ADAPTIVE_MODE, PlasticityPolicy,
            TRANSITIONED_POLICY_STATE_SCHEMA, TRANSITIONED_POLICY_VERSION,
            advance_candidate_policy, apply_promotion_transition,
        )
        parent = PlasticityPolicy(
            row_ages=(IdentityRowAge(0, 1, 3), IdentityRowAge(0, 2, 8)))
        receipt = self._promotion_receipt()
        with patch(
            "bilqis_mlx.runtime.plasticity_promotion."
            "require_accepted_promotion_transition",
            side_effect=lambda value: value,
        ):
            transitioned = apply_promotion_transition(parent, receipt)
            self.assertEqual(transitioned.mode, ADAPTIVE_MODE)
            self.assertEqual(transitioned.accepted_fast_since_full, 0)
            self.assertIs(transitioned.row_ages, parent.row_ages)
            self.assertEqual(
                transitioned.policy_version, TRANSITIONED_POLICY_VERSION)
            self.assertEqual(
                transitioned.schema_version, TRANSITIONED_POLICY_STATE_SCHEMA)
            self.assertEqual(
                transitioned.mode_transition.promotion_receipt_sha256,
                receipt.digest)
            self.assertIs(
                apply_promotion_transition(transitioned, receipt), transitioned)
            cold = PlasticityPolicy.from_record(
                json.loads(json.dumps(transitioned.to_record())))
            self.assertEqual(cold, transitioned)
            advanced = advance_candidate_policy(
                cold, teacher_requests_full=False, accepted=True,
                participating_rows=((0, 1),))
            self.assertEqual(advanced.accepted_fast_since_full, 1)
            self.assertEqual(advanced.mode_transition, cold.mode_transition)
            self.assertEqual(
                tuple(item.accepted_age for item in advanced.row_ages), (4, 8))

    def test_debt_transition_persists_and_conflicting_receipt_fails_closed(self):
        from bilqis_mlx.learning.atlas_plasticity import (
            PlasticityPolicy, apply_promotion_transition,
        )
        debt_receipt = self._promotion_receipt(
            outcome="PROMOTED_WITH_DEBT",
            carried_debt=("A.TWO",),
            digest="f" * 64,
        )
        with patch(
            "bilqis_mlx.runtime.plasticity_promotion."
            "require_accepted_promotion_transition",
            side_effect=lambda value: value,
        ):
            transitioned = apply_promotion_transition(
                PlasticityPolicy(), debt_receipt)
            self.assertEqual(
                transitioned.mode_transition.carried_debt, ("A.TWO",))
            self.assertEqual(
                transitioned.mode_transition.outcome, "PROMOTED_WITH_DEBT")
            with self.assertRaises(BilqisError):
                apply_promotion_transition(
                    transitioned,
                    self._promotion_receipt(digest="1" * 64))

    def test_legacy_adaptive_record_cannot_be_retroactively_upgraded(self):
        from bilqis_mlx.learning.atlas_plasticity import (
            PlasticityPolicy, apply_promotion_transition,
        )
        legacy = PlasticityPolicy(mode="ADAPTIVE", accepted_fast_since_full=2)
        cold = PlasticityPolicy.from_record(legacy.to_record())
        self.assertIsNone(cold.mode_transition)
        with patch(
            "bilqis_mlx.runtime.plasticity_promotion."
            "require_accepted_promotion_transition",
            side_effect=lambda value: value,
        ):
            with self.assertRaises(BilqisError):
                apply_promotion_transition(cold, self._promotion_receipt())
