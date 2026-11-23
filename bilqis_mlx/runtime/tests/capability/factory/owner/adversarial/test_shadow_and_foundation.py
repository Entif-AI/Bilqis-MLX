"""Shadow-target and Foundation C05 owner regressions."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import mlx.core as mx

import bilqis_mlx.learning.atlas_acceptance as acceptance_owner
from bilqis_mlx.learning.atlas_acceptance import mint_acceptance_binding
from bilqis_mlx.learning.atlas_candidate import CandidateTransaction
from bilqis_mlx.learning.atlas_retention_decision import (
    CandidateRetentionDecision, _issued_decision_baseline_ledger_sha256,
    issue_factory_retention_decision,
)
from bilqis_mlx.runtime.baseline.lifecycle import BaselineLifecycleState
from bilqis_mlx.runtime.capability_retention import Decision, DecisionStatus
import bilqis_mlx.runtime.factory_retention_owner as owner
import bilqis_mlx.runtime._factory_retention_support as retention_support
from bilqis_mlx.runtime.factory_retention_owner import FactoryRetentionEvaluation
from bilqis_mlx.runtime.tests.capability.factory.retention.diagnostics.factory_retention_fixed_diagnostic import (
    _optimizer_delta_summary,
)

from .support import (
    _evaluate_foundation_owner, _foundation_owner_fixture,
    _foundation_retention_plan,
)


class FactoryRetentionOwnerShadowTests(unittest.TestCase):
    def test_learning_first_candidate_preserves_source_independence_coordinates(self):
        candidate = object.__new__(CandidateTransaction)
        object.__setattr__(candidate, "learning_first", True)
        object.__setattr__(candidate, "training_authorities", ())
        object.__setattr__(candidate, "step_proofs", ())
        object.__setattr__(candidate, "update_steps", 1)
        object.__setattr__(candidate, "training_source_coordinates", (
            ("B.IDBOOLOPS", "family-a", "episode-a"),
            ("B.IDBOOLOPS", "family-a", "episode-b"),
        ))
        self.assertEqual(
            owner._training_exclusions(candidate),
            (("family-a",), ("episode-a", "episode-b")))
        self.assertEqual(owner._training_capabilities(candidate), ("B.IDBOOLOPS",))

    def test_multifidelity_shadow_target_is_observational_and_reuses_parent_score(self):
        target = "B.IDBOOLOPS"
        source, candidate, *_ = _foundation_owner_fixture()
        plan, target_plan, instrument = _foundation_retention_plan(target)
        source.require_accepted_runtime = Mock()
        parent = SimpleNamespace()
        candidate_bundle = SimpleNamespace()
        candidate_state = SimpleNamespace()
        cache = SimpleNamespace()
        candidate_assessment = SimpleNamespace(score=Mock(return_value=(4, 6)))
        parent_assessment = SimpleNamespace(score=Mock(return_value=(3, 6)))
        with patch.multiple(
                owner,
                _candidate_from_live_parent=Mock(return_value=(
                    parent, candidate_bundle, candidate_state, cache)),
                require_current_retention_source_rows=Mock(return_value=(
                    plan, target_plan, ((target, 7, ({"id": "row"},)),))),
                split_cached_rows=Mock(return_value=((7, ({"id": "row"},)), ())),
                _instruments=Mock(return_value=(instrument,)),
                EvaluationCohort=Mock(return_value=object()),
                case_census_digest=Mock(return_value="7" * 64),
                factory_complete_solver=Mock(side_effect=(
                    (object(), "c" * 64), (object(), "p" * 64))),
                evaluate_capabilities=Mock(side_effect=(
                    candidate_assessment, parent_assessment))):
            first = owner.measure_current_retention_shadow_target(
                source, candidate, "artifact", target, run_dir=Path("unused"))
        self.assertEqual(first["target_correct_delta"], 1)
        self.assertEqual(first["parent_correct"], 3)
        self.assertEqual(first["candidate_correct"], 4)
        self.assertFalse(first["final_c05_authority"])
        self.assertFalse(first["actual_authority_changed"])
        source.require_accepted_runtime.assert_called_once_with(Path("unused"))

        candidate_assessment = SimpleNamespace(score=Mock(return_value=(5, 6)))
        solver = Mock(return_value=(object(), "d" * 64))
        evaluator = Mock(return_value=candidate_assessment)
        bound = Mock(return_value=(parent, candidate_bundle, candidate_state, cache))
        with patch.multiple(
                owner,
                _candidate_from_bound_parent=bound,
                _candidate_from_live_parent=Mock(side_effect=AssertionError(
                    "bound shadow probe must not reload parent")),
                require_current_retention_source_rows=Mock(return_value=(
                    plan, target_plan, ((target, 7, ({"id": "row"},)),))),
                split_cached_rows=Mock(return_value=((7, ({"id": "row"},)), ())),
                _instruments=Mock(return_value=(instrument,)),
                EvaluationCohort=Mock(return_value=object()),
                case_census_digest=Mock(return_value="7" * 64),
                factory_complete_solver=solver,
                evaluate_capabilities=evaluator):
            later = owner.measure_current_retention_shadow_target(
                source, candidate, "artifact", target, run_dir=Path("unused"),
                parent_correct=3, accepted_parent=parent, execution_cache=cache)
        self.assertEqual(later["target_correct_delta"], 2)
        bound.assert_called_once_with(
            parent, cache, candidate, canonical_identity_required=False)
        self.assertEqual(solver.call_count, 1)
        self.assertEqual(evaluator.call_count, 1)
        self.assertEqual(source.require_accepted_runtime.call_count, 1)

    def test_observational_shadow_does_not_mint_canonical_candidate_identity(self):
        retained = object()
        preview = object()
        custody = SimpleNamespace(
            run_id="run", generation=3, manifest_sha256="1" * 64,
            topology_digest="2" * 64, extents_digest="3" * 64)
        transaction = SimpleNamespace(
            update_steps=2, parent=SimpleNamespace(custody=custody),
            motif_transition=None)
        parent = SimpleNamespace(
            retained_state=retained,
            topology=SimpleNamespace(digest="2" * 64),
            extents=SimpleNamespace(digest="3" * 64))
        cache = SimpleNamespace(
            run_id="run", generation=3, accepted_manifest_sha256="1" * 64)

        with patch.object(
                retention_support, "candidate_identity_for_canonical_consumer",
                return_value="4" * 64), patch.object(
                    retention_support, "resolve_candidate",
                    return_value=preview), patch.object(
                        retention_support, "bind_candidate_identity_or_fallback",
                        side_effect=AssertionError("shadow canonical identity hash")), patch.object(
                            retention_support, "derive_successor_bundle",
                            return_value="successor"):
            result = retention_support._candidate_from_bound_parent(
                parent, cache, transaction, canonical_identity_required=False)

        self.assertEqual(result, (parent, "successor", preview, cache))

    def test_retention_boundary_still_mints_canonical_candidate_identity(self):
        retained = object()
        preview = object()
        custody = SimpleNamespace(
            run_id="run", generation=3, manifest_sha256="1" * 64,
            topology_digest="2" * 64, extents_digest="3" * 64)
        transaction = SimpleNamespace(
            update_steps=2, parent=SimpleNamespace(custody=custody),
            motif_transition=None)
        parent = SimpleNamespace(
            retained_state=retained,
            topology=SimpleNamespace(digest="2" * 64),
            extents=SimpleNamespace(digest="3" * 64))
        cache = SimpleNamespace(
            run_id="run", generation=3, accepted_manifest_sha256="1" * 64)
        canonical = Mock()

        with patch.object(
                retention_support, "candidate_identity_for_canonical_consumer",
                return_value="4" * 64), patch.object(
                    retention_support, "resolve_candidate",
                    return_value=preview), patch.object(
                        retention_support, "bind_candidate_identity_or_fallback",
                        canonical), patch.object(
                            retention_support, "derive_successor_bundle",
                            return_value="successor"):
            result = retention_support._candidate_from_bound_parent(
                parent, cache, transaction)

        canonical.assert_called_once_with(preview, "2" * 64, "3" * 64)
        self.assertEqual(result, (parent, "successor", preview, cache))

    def test_optimizer_delta_summary_distinguishes_decay_only_from_gradient_driven_change(self):
        parent = SimpleNamespace(retained_state=SimpleNamespace(
            optimizer=SimpleNamespace(parameters={
                "blocks.0.query": mx.array([1.0], dtype=mx.float32),
                "readout.query": mx.array([2.0], dtype=mx.float32)})))
        candidate = SimpleNamespace(optimizer=SimpleNamespace(parameters={
            "blocks.0.query": mx.array([0.99], dtype=mx.float32),
            "readout.query": mx.array([2.1], dtype=mx.float32)}))
        gradient = SimpleNamespace(gradients={
            "blocks.0.query": mx.array([0.0], dtype=mx.float32),
            "readout.query": mx.array([3.0], dtype=mx.float32)})
        summary = _optimizer_delta_summary(parent, candidate, gradient)
        self.assertEqual(summary["blocks"]["nonzero_gradient_parameters"], 0)
        self.assertEqual(summary["blocks"]["changed_parameters"], 1)
        self.assertEqual(summary["blocks"]["zero_gradient_changed_parameters"], 1)
        self.assertEqual(summary["readout"]["nonzero_gradient_parameters"], 1)
        self.assertEqual(summary["readout"]["changed_parameters"], 1)
        self.assertEqual(summary["readout"]["zero_gradient_changed_parameters"], 0)

    def test_foundation_owner_draws_only_the_fresh_target_before_local_protection(self):
        fixture = _foundation_owner_fixture()
        _, _, target, _, fresh, policy_factory, _ = fixture
        result = _evaluate_foundation_owner(*fixture)
        self.assertIsInstance(result, FactoryRetentionEvaluation)
        result.__post_init__()
        issued = issue_factory_retention_decision(result)
        self.assertTrue(issued.accepted)
        self.assertEqual(issued.parent_generation, "d" * 64)
        self.assertEqual(issued.candidate_generation, "d" * 64)
        self.assertIsNone(result.parent_assessment_cache)
        self.assertEqual(result.candidate_generation_authority_sha256, "f" * 64)
        self.assertEqual(
            _issued_decision_baseline_ledger_sha256(issued), result.baseline_ledger.digest)
        self.assertEqual(issued.evaluated_capability_ids, (target,))
        self.assertEqual(issued.retention_protection_plan_sha256, "3" * 64)
        cold = CandidateRetentionDecision.from_record(issued.to_record())
        self.assertEqual(cold.fields["evaluated_capability_ids"], (target,))
        self.assertEqual(cold.fields["retention_protection_plan_sha256"], "3" * 64)
        self.assertIsNotNone(result.baseline_transition)
        self.assertIs(
            result.baseline_ledger.state_for(result.baseline_transition.measurement.comparison),
            BaselineLifecycleState.BASELINE_ESTABLISHED)
        self.assertTrue(all(call.args[2] == () for call in policy_factory.call_args_list))
        retained = SimpleNamespace(optimizer_step=1, step_proofs=())
        with patch.object(acceptance_owner, "candidate_identity_digest", return_value="d" * 64):
            bound = mint_acceptance_binding(
                issued, retained, run_id="fixture-run", generation=1,
                feature_sha256="a" * 64, generation_authority_sha256="f" * 64)
        self.assertEqual(
            acceptance_owner._issued_acceptance_baseline_ledger_sha256(bound),
            result.baseline_ledger.digest)
        fresh.assert_called_once()
        self.assertEqual(fresh.call_args.args[1], (target,))

    def test_target_first_rejection_issues_c05_authority_without_championship_evidence(self):
        fixture = _foundation_owner_fixture()
        rejection = Decision(
            DecisionStatus.REJECT, "NO_MEASURABLE_TARGET_GAIN",
            "a" * 64, "b" * 64, "c" * 64, "d" * 64,
            evaluated_capability_ids=(fixture[2],),
            retention_protection_plan_sha256="3" * 64)
        result = _evaluate_foundation_owner(*fixture, target_gate_decision=rejection)
        self.assertIsInstance(result, FactoryRetentionEvaluation)
        result.__post_init__()
        issued = issue_factory_retention_decision(result)
        self.assertFalse(issued.accepted)
        self.assertEqual(issued.reason, "NO_MEASURABLE_TARGET_GAIN")
        self.assertIsNone(result.championship_cohort)
        self.assertIsNone(result.championship_assessment)
