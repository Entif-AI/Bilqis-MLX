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


class PreparedFactoryEvaluationPolicyTests(unittest.TestCase):
    def test_learning_first_ragged_chunk_splits_quadratic_padding_waste(self):
        widths = (10, 12, 18, 18, 24, 28)
        items = tuple(SimpleNamespace(width=width) for width in widths)
        with patch.object(batching, "_positions", side_effect=lambda item: item.width):
            groups = batching._learning_first_partition_indices(items)
        self.assertEqual(groups, ((0, 1, 2, 3), (4, 5)))
        one = len(widths) * max(widths) ** 2
        split = sum(
            len(group) * max(widths[index] for index in group) ** 2
            for group in groups)
        self.assertLessEqual(split, one * 0.8)

    def test_learning_first_uniform_chunk_stays_single_launch(self):
        widths = (22, 22, 24, 24, 24, 24)
        items = tuple(SimpleNamespace(width=width) for width in widths)
        with patch.object(batching, "_positions", side_effect=lambda item: item.width):
            groups = batching._learning_first_partition_indices(items)
        self.assertEqual(groups, ((0, 1, 2, 3, 4, 5),))

    def test_learning_first_ragged_execution_restores_original_case_order(self):
        widths = (28, 10, 24, 12, 18, 18)
        items = []
        for index, width in enumerate(widths):
            item = object.__new__(batching.PreparedFactoryEvaluation)
            object.__setattr__(item, "batch", object())
            object.__setattr__(item, "plan", object())
            object.__setattr__(item, "authority", object())
            object.__setattr__(item, "ordinal", index)
            object.__setattr__(item, "width", width)
            items.append(item)
        items = tuple(items)

        def execute(_parameters, chunk, _on_launch, _execution_binding):
            return tuple(f"output-{item.ordinal}" for item in chunk)

        with (
            evidence_mode(strict=False),
            patch.object(batching, "_batchable", return_value=True),
            patch.object(batching, "_compatible", return_value=True),
            patch.object(batching, "_capacity", side_effect=lambda proposed: len(proposed)),
            patch.object(batching, "_positions", side_effect=lambda item: item.width),
            patch.object(batching, "_execute_chunk", side_effect=execute) as shared,
        ):
            outputs = batching.batched_factory_outputs(object(), items)

        self.assertEqual(outputs, tuple(f"output-{index}" for index in range(6)))
        self.assertEqual(shared.call_count, 2)
        self.assertEqual(
            tuple(tuple(item.ordinal for item in call.args[1])
                  for call in shared.call_args_list),
            ((1, 3, 4, 5), (0, 2)),
        )

    def test_strict_ragged_execution_keeps_single_shared_launch(self):
        widths = (28, 10, 24, 12, 18, 18)
        items = []
        for index, width in enumerate(widths):
            item = object.__new__(batching.PreparedFactoryEvaluation)
            object.__setattr__(item, "batch", object())
            object.__setattr__(item, "plan", object())
            object.__setattr__(item, "authority", object())
            object.__setattr__(item, "ordinal", index)
            object.__setattr__(item, "width", width)
            items.append(item)
        items = tuple(items)

        with (
            evidence_mode(strict=True),
            patch.object(batching, "_batchable", return_value=True),
            patch.object(batching, "_compatible", return_value=True),
            patch.object(batching, "_capacity", side_effect=lambda proposed: len(proposed)),
            patch.object(batching, "_positions", side_effect=lambda item: item.width),
            patch.object(
                batching, "_execute_chunk",
                return_value=tuple(f"output-{index}" for index in range(6))) as shared,
        ):
            outputs = batching.batched_factory_outputs(object(), items)

        self.assertEqual(outputs, tuple(f"output-{index}" for index in range(6)))
        shared.assert_called_once()

    def test_learning_first_shared_outputs_skip_logit_attestation(self):
        output = object()
        with (
            evidence_mode(strict=False),
            patch.object(
                batching, "attest_issued_outputs",
                side_effect=AssertionError("learning-first output attestation")),
            patch.object(batching, "live_issued_output", return_value=True) as live,
        ):
            self.assertTrue(batching._issued_outputs_valid(
                (output,), numerically_finite=True))
        live.assert_called_once_with(output)

    def test_learning_first_prepared_row_skips_recursive_proof_revalidation(self):
        authority = object.__new__(FactoryTaskAuthority)
        object.__setattr__(authority, "generation_binding", "1" * 64)
        batch = object.__new__(BamfCompiledBatch)
        object.__setattr__(batch, "task_authority", authority)
        plan = object.__new__(AnswerPlan)
        object.__setattr__(plan, "generation_binding", "1" * 64)
        with (
            evidence_mode(strict=False),
            patch.object(BamfCompiledBatch, "__post_init__",
                         side_effect=AssertionError("learning-first batch proof")),
            patch.object(AnswerPlan, "__post_init__",
                         side_effect=AssertionError("learning-first plan proof")),
            patch.object(FactoryTaskAuthority, "__post_init__",
                         side_effect=AssertionError("learning-first authority proof")),
        ):
            prepared = batching.PreparedFactoryEvaluation(batch, plan, authority)
        self.assertIs(prepared.batch, batch)
