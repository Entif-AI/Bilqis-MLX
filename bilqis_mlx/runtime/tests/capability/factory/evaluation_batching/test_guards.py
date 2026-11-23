"""C05 #1167 fixed-school MLX batching equivalence and resource witnesses."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import mlx.core as mx
from bilqis_mlx.errors import BilqisError
import bilqis_mlx.learning.source_atoms.embedding as source_embedding
import bilqis_mlx.runtime.backbone_identity as backbone_identity
from bilqis_mlx.runtime.capability_retention import (
    EvidenceKind, EvaluationCohort, case_census_digest,
    candidate_work_disposition, evaluate_capabilities,
)
from bilqis_mlx.runtime.factory_complete_solver import (
    factory_complete_solver, factory_evaluation_instrument,
)
import bilqis_mlx.runtime.factory_evaluation_batching as batching
import bilqis_mlx.runtime.factory_complete_solver as complete_solver_module
from bilqis_mlx.runtime.factory_evaluation_batching import _capacity
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.atlas_model_contracts import BamfCompiledBatch
from bilqis_mlx.runtime.factory_task_authority import FactoryTaskAuthority
from bilqis_mlx.learning.atlas_readout import AnswerPlan
from bilqis_mlx.runtime.factory_evaluation_compiler import compile_factory_evaluation_batch
from bilqis_mlx.runtime.tests.batch.factory.factory_training_bridge_support import (
    FactoryTrainingBridgeFixture,
)



from .support import FactoryEvaluationBatchingTests as FactoryEvaluationBatchingSupport

class FactoryEvaluationBatchingGuardTests(FactoryEvaluationBatchingSupport):
    def test_generation_digest_is_issued_once_for_batched_and_scalar_fallback(self):
        instruments = self._instruments()
        goals = tuple(item.case.goal for item in instruments)
        original = backbone_identity.bamf_parameter_tree_digest

        with patch.object(
                backbone_identity, "bamf_parameter_tree_digest",
                wraps=original) as digest:
            batched, generation = factory_complete_solver(
                self.context, self.candidate, str(self.artifact), instruments)
            self.assertEqual(digest.call_count, 1)
            batched.evaluate_cases(goals, generation)
            self.assertEqual(digest.call_count, 1)

        with patch.object(
                backbone_identity, "bamf_parameter_tree_digest",
                wraps=original) as digest, patch.object(
                batching, "_positions", return_value=97):
            scalar, generation = factory_complete_solver(
                self.context, self.candidate, str(self.artifact), instruments)
            self.assertEqual(digest.call_count, 1)
            scalar.evaluate_cases(goals, generation)
            self.assertEqual(digest.call_count, 1)

    def test_repeated_batch_evaluation_rejects_task_drift_for_cached_goal_id(self):
        instruments = self._instruments()
        _scalar, batched, generation = self._solver_pair(instruments)
        goals = tuple(item.case.goal for item in instruments)
        batched.evaluate_cases(goals, generation)
        drifted = replace(
            goals[0],
            source_visible_bindings=tuple(sorted((
                *goals[0].source_visible_bindings,
                "source:drift",
            ))),
        )

        with self.assertRaises(BilqisError) as caught:
            batched.evaluate_cases((drifted, *goals[1:]), generation)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C05_FACTORY_SOLVER_SOURCE_DRIFT",
        )

    def test_over_96_compiled_width_falls_back_to_scalar_without_semantic_drift(self):
        instruments = self._instruments()
        scalar, batched, generation = self._solver_pair(instruments)
        goals = tuple(item.case.goal for item in instruments)
        scalar_measurements = scalar.evaluate_cases(goals, generation)

        with patch.object(batching, "_positions", return_value=97):
            batch_measurements = batched.evaluate_cases(goals, generation)

        self.assertEqual(
            tuple((result.replay_record(), contract)
                  for result, contract in scalar_measurements),
            tuple((result.replay_record(), contract)
                  for result, contract in batch_measurements),
        )
        telemetry = batched.telemetry_for()
        self.assertEqual(telemetry["shared_backbone_launches"], 0)
        self.assertEqual(telemetry["scalar_neural_launches"], self.EACH)

    def test_bounded_chunk_splitting_is_deterministic(self):
        instruments = self._instruments()
        _scalar, batched, generation = self._solver_pair(instruments)
        goals = tuple(item.case.goal for item in instruments)

        with patch.object(
                batching, "_capacity",
                side_effect=lambda items: min(2, len(items))):
            batched.evaluate_cases(goals, generation)

        telemetry = batched.telemetry_for()
        self.assertEqual(telemetry["shared_backbone_launches"], 2)
        self.assertEqual(telemetry["shared_backbone_rows"], self.EACH)
        self.assertEqual(telemetry["largest_shared_rows"], 2)

    def test_batch_compatibility_failure_propagates_instead_of_falling_back(self):
        instruments = self._instruments()
        _scalar, batched, generation = self._solver_pair(instruments)
        goals = tuple(item.case.goal for item in instruments)

        with patch.object(
                batching, "_compatible",
                side_effect=RuntimeError("custody validation failed")):
            with self.assertRaisesRegex(RuntimeError, "custody validation failed"):
                batched.evaluate_cases(goals, generation)

    def test_b11_row_decode_rejects_task_plan_custody_drift(self):
        instruments = self._instruments()
        original = complete_solver_module.task_goal_route_plan

        def drifted_plan(*args, **kwargs):
            return replace(original(*args, **kwargs), refinement_request=None)

        with patch.object(complete_solver_module, "task_goal_route_plan", drifted_plan):
            _scalar, batched, generation = self._solver_pair(instruments)
            goals = tuple(item.case.goal for item in instruments)
            with self.assertRaises(BilqisError) as caught:
                batched.evaluate_cases(goals, generation)
        self.assertEqual(
            caught.exception.context["reason"],
            "B11_FORWARD_TASK_PLAN_CUSTODY_MISMATCH",
        )
