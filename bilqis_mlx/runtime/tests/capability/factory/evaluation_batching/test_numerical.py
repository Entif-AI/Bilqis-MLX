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

class FactoryEvaluationBatchingNumericalTests(FactoryEvaluationBatchingSupport):
    def test_fixed_school_batch_matches_scalar_and_reduces_backbone_launches(self):
        instruments = self._instruments()
        scalar, batched, generation = self._solver_pair(instruments)
        goals = tuple(item.case.goal for item in instruments)
        widths = tuple(len(compile_factory_evaluation_batch(
            self.context, self.candidate, str(self.artifact), item.source_row,
            source_seed=item.source_seed,
            source_each=item.source_each,
        ).compiled.compiled.rows[0].positions) for item in instruments)
        self.assertGreater(len(set(widths)), 1)

        scalar_measurements = scalar.evaluate_cases(goals, generation)
        batch_measurements = batched.evaluate_cases(goals, generation)

        self.assertEqual(
            tuple((result.replay_record(), contract)
                  for result, contract in scalar_measurements),
            tuple((result.replay_record(), contract)
                  for result, contract in batch_measurements),
        )
        scalar_telemetry = scalar.telemetry_for()
        batch_telemetry = batched.telemetry_for()
        self.assertEqual(scalar_telemetry["scalar_neural_launches"], self.EACH)
        self.assertEqual(batch_telemetry["scalar_neural_launches"], 0)
        self.assertGreaterEqual(batch_telemetry["shared_backbone_rows"], 2)
        self.assertLess(batch_telemetry["shared_backbone_launches"], self.EACH)
        self.assertLessEqual(batch_telemetry["largest_shared_positions"], 96)

    def test_refinement_batch_matches_scalar_without_rowwise_decode(self):
        instruments = self._instruments_for("B.AND", seed=37211, each=4)
        scalar, batched, generation = self._solver_pair(instruments)
        goals = tuple(item.case.goal for item in instruments)
        scalar_measurements = scalar.evaluate_cases(goals, generation)
        original_decode = batching._decode_bamf_producer_row

        with patch.object(
                batching, "_decode_bamf_producer_row",
                wraps=original_decode) as decode:
            batch_measurements = batched.evaluate_cases(goals, generation)

        self.assertEqual(
            tuple((result.replay_record(), contract)
                  for result, contract in scalar_measurements),
            tuple((result.replay_record(), contract)
                  for result, contract in batch_measurements),
        )
        self.assertEqual(decode.call_count, 0)

    def test_default_shared_batch_uses_receipt_free_backbone_trace(self):
        instruments = self._instruments()
        _scalar, batched, generation = self._solver_pair(instruments)
        goals = tuple(item.case.goal for item in instruments)
        original = batching.start_source_backbone_producer

        with patch.object(
                batching, "start_source_backbone_producer",
                wraps=original) as producer:
            batched.evaluate_cases(goals, generation)

        self.assertGreater(producer.call_count, 0)
        self.assertTrue(all(call.kwargs.get("trace") is True
                            for call in producer.call_args_list))

    def test_learning_first_shared_batch_prepares_source_parameters_once(self):
        instruments = self._instruments()
        _scalar, batched, generation = self._solver_pair(instruments)
        goals = tuple(item.case.goal for item in instruments)
        original = source_embedding._source_embedding_parameters

        with patch.object(
                source_embedding, "_source_embedding_parameters",
                wraps=original) as prepare:
            batched.evaluate_cases(goals, generation)

        self.assertEqual(prepare.call_count, 1)

    def test_assessment_and_work_disposition_are_scalar_batch_identical(self):
        instruments = self._instruments()
        scalar, batched, generation = self._solver_pair(instruments)
        cohort = self._cohort(instruments)
        scalar_assessment = evaluate_capabilities(scalar, cohort, generation)
        batch_assessment = evaluate_capabilities(batched, cohort, generation)

        self.assertEqual(scalar_assessment.digest(), batch_assessment.digest())
        self.assertEqual(
            candidate_work_disposition(scalar_assessment, self.CAPABILITY),
            candidate_work_disposition(batch_assessment, self.CAPABILITY),
        )

    def test_repeated_batch_evaluation_does_not_prelaunch_after_composition_cache(self):
        instruments = self._instruments()
        _scalar, batched, generation = self._solver_pair(instruments)
        goals = tuple(item.case.goal for item in instruments)
        first = batched.evaluate_cases(goals, generation)
        before = batched.telemetry_for()
        second = batched.evaluate_cases(goals, generation)
        after = batched.telemetry_for()

        self.assertEqual(before, after)
        self.assertEqual(
            tuple(result.answer for result, _contract in first),
            tuple(result.answer for result, _contract in second),
        )
