"""C05 #1167 fixed-school MLX batching equivalence and resource witnesses."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

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


class FactoryBatchResourcePolicyTests(unittest.TestCase):
    @staticmethod
    def _item(position_count):
        row = SimpleNamespace(positions=(None,) * position_count)
        compiled = SimpleNamespace(compiled=SimpleNamespace(rows=(row,)))
        return SimpleNamespace(batch=SimpleNamespace(compiled=compiled))

    def test_compiled_position_budget_falls_back_above_legacy_width(self):
        self.assertEqual(_capacity((self._item(97), self._item(97))), 1)

    def test_compiled_position_budget_bounds_activation_and_attention_work(self):
        items = tuple(self._item(96) for _ in range(30))
        self.assertEqual(_capacity(items), 24)
        items = tuple(self._item(48) for _ in range(60))
        self.assertEqual(_capacity(items), 48)


def test_refinement_bearing_shared_batch_stays_vectorized():
    features = SimpleNamespace(semantic_release="test-release")
    extents = SimpleNamespace(digest="extents")
    owner = SimpleNamespace(require=Mock(
        side_effect=AssertionError("learning-first Atlas feature proof")))
    active = SimpleNamespace(active_indices=())
    batch = SimpleNamespace(
        compiled=SimpleNamespace(features=features, extents=extents),
        atlas_feature_artifact_owner=owner,
        active_semantic_rows=active,
        sources=(object(),),
        feature_schema=object(),
    )
    plan = SimpleNamespace(snapshot=object(), generation_binding="generation")
    items = tuple(SimpleNamespace(batch=batch, plan=plan) for _ in range(2))
    combined = SimpleNamespace(features=features, extents=extents)
    hidden = mx.zeros((2, 1, 4), dtype=mx.float32)
    refined = mx.ones((2, 1, 4), dtype=mx.float32)
    trajectory = (mx.zeros((2,), dtype=mx.uint32),)
    route_logits = (mx.zeros((2, 1), dtype=mx.float32),)
    refinement = (object(), (SimpleNamespace(passes=1),))

    with patch.object(batching, "_batchable", return_value=True), patch.object(
            batching, "_compatible", return_value=True), patch.object(
                batching, "_capacity", return_value=2), patch.object(
                    batching, "_combine", return_value=combined), patch.object(
                        batching, "model_backend",
                        return_value=SimpleNamespace(topology=object())), patch.object(
                            batching, "require_execution_generation_binding",
                            side_effect=AssertionError(
                                "learning-first duplicate generation proof")), patch.object(
                                batching, "semantic_bank_views", return_value=object()), patch.object(
                                    batching, "start_source_backbone_producer",
                                    return_value=object()), patch.object(
                                        batching, "finalize_source_backbone_hidden",
                                        return_value=hidden), patch.object(
                                            batching, "_prediction_refinement_selection",
                                            return_value=refinement), patch.object(
                                                batching, "batched_refine_hidden",
                                                return_value=refined) as refine, patch.object(
                                                    batching, "prepare_route_microbatch_inference_kernel",
                                                    return_value=object()), patch.object(
                                                        batching, "route_microbatch_trajectory",
                                                        return_value=(trajectory, route_logits)), patch.object(
                                                            batching, "_route_output_from_materialized_logits",
                                                            side_effect=(object(), object())), patch.object(
                                                                batching, "attest_issued_outputs",
                                                                return_value=True), patch.object(
                                                                    batching, "live_issued_output",
                                                                    return_value=True), patch.object(
                                                                    batching, "_decode_bamf_producer_row",
                                                                    side_effect=AssertionError(
                                                                        "rowwise decode used")):
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
        with evidence_mode(strict=False):
            outputs = batching._execute_chunk(
                {"parameter": mx.zeros((1,), dtype=mx.float32)},
                items, None, object())

    assert len(outputs) == 2
    refine.assert_called_once()


if __name__ == "__main__":
    unittest.main()
