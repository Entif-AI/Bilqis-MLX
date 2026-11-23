"""Production-shaped proof for the authority-light BAMF source path."""
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import mlx.core as mx

import bilqis_mlx.learning.atlas_engram_reads.source_owner as motif_read_impl
from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_operator.session import _execution_context
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.factory_candidate_components import _resource_plan
from bilqis_mlx.runtime.factory_candidate_cost import realized_candidate_cost
from bilqis_mlx.runtime.factory_training_bridge import prepare_factory_training_batch
from bilqis_mlx.runtime.tests.batch.training.visit_provenance_support import visit_provenance

from .pre_neural_journey_support import (
    PreNeuralJourneySupport, historical_school_release, journey_source,
    portable_atlas_snapshot, wide_shape_patch,
)


class LearningFirstSourcePathTests(PreNeuralJourneySupport, unittest.TestCase):
    def test_candidate_cost_reports_authority_free_rows_without_requalification(self):
        compiled_row = SimpleNamespace(positions=(object(), object()))
        compiled = SimpleNamespace(
            source_execution_authority=None,
            compiled=SimpleNamespace(compiled=SimpleNamespace(rows=(compiled_row,))))
        prepared = SimpleNamespace(compiled_rows=(compiled, compiled))
        resource_plan = SimpleNamespace(
            microbatch_size=2, groups=((0, 1),), estimated_peak_bytes=1)
        memory_budget = SimpleNamespace(allocation_bytes=2)
        transaction = SimpleNamespace(update_steps=1)
        feature_context = SimpleNamespace(
            atlas_reload_count=0, feature_manifest_rebuild_count=0)
        stage_metrics = {
            "pre_neural_source_compile_wall_seconds": 0.0,
            "currentness_binding_wall_seconds": 0.0,
            "optimizer_admission_wall_seconds": 0.0,
            "motif_staging_wall_seconds": 0.0,
            "candidate_terminal_step": False,
        }
        gradient = SimpleNamespace(_performance_observation={})
        started = time.perf_counter()

        with evidence_mode(strict=False):
            cost = realized_candidate_cost(
                started, started, mx.array(1.0), prepared, resource_plan,
                memory_budget, transaction, feature_context, False,
                (1, 1, 1, 0, 0.1), stage_metrics, gradient,
                invalid=lambda reason: (_ for _ in ()).throw(AssertionError(reason)))

        self.assertEqual(cost["b11_source_authority_bound_rows"], 0)
        self.assertEqual(cost["b11_source_authority_free_rows"], 2)
        self.assertEqual(cost["b11_source_cold_requalification_rows"], 0)
        with evidence_mode(strict=True), self.assertRaisesRegex(
                AssertionError, "FACTORY_CANDIDATE_SOURCE_EXECUTION_AUTHORITY_MISSING"):
            realized_candidate_cost(
                started, started, mx.array(1.0), prepared, resource_plan,
                memory_budget, transaction, feature_context, False,
                (1, 1, 1, 0, 0.1), stage_metrics, gradient,
                invalid=lambda reason: (_ for _ in ()).throw(AssertionError(reason)))

    def test_factory_batch_bypasses_strict_source_evidence_ceremony(self):
        self.current, self.parent_graph = historical_school_release()
        snapshot = portable_atlas_snapshot()
        schema, features, atlas_selection = journey_source(snapshot)
        with wide_shape_patch(len(snapshot.abi_entries)):
            self.publish_matching_genesis(snapshot, schema, features)
            with self.journey_mounts(snapshot, schema, features, atlas_selection):
                parent, context, atlas_path, feature_path = _execution_context(self.run)
                rows = tuple(context.draw_rows(
                    seed=12345, capability="B.AND", each=4))
                execution = context.release.execution_plan.capability_map["B.AND"]
                delivery = describe_delivered_teaching(
                    context.release, "B.AND", execution.teaching_option_ids[0], rows)
                selected_source_authority = context.bind_rows(
                    rows, seed=12345, capability="B.AND", each=4)
                generation = execution_generation_digest(
                    parent.retained_state.optimizer.parameters,
                    spec=parent.topology, extents=parent.extents)
                with evidence_mode(strict=False):
                    started = time.perf_counter()
                    with patch.object(
                            type(context), "bind_rows",
                            side_effect=AssertionError("learning-first source redraw")), patch(
                            "bilqis_mlx.runtime.factory_training_source."
                            "authorize_public_formal_prefix",
                            side_effect=AssertionError("learning-first prefix authority")):
                        prepared = prepare_factory_training_batch(
                            context, parent, atlas_path, feature_path, rows, generation,
                            capability="B.AND", delivery=delivery, requested_count=4,
                            source_seed=12345, source_each=4, optimizer_step_seed=7,
                            visit_provenance=visit_provenance("B.AND"),
                            teacher_strategy={"policy": "learning-first"},
                            selected_source_authority=selected_source_authority)
                        resource_plan, _memory_budget = _resource_plan(
                            prepared, parent, None)
                        compiled = prepared.compiled_rows[0]
                        row = compiled.compiled.compiled.rows[0]
                        with patch.object(
                                motif_read_impl, "source_qualified_motif_context",
                                side_effect=AssertionError("learning-first motif replay")), \
                                patch.object(
                                    motif_read_impl, "lookup_source_pinned_frame_schema",
                                    side_effect=AssertionError("learning-first schema replay")), \
                                patch.object(
                                    motif_read_impl, "motif_gate_features",
                                    return_value=SimpleNamespace(
                                        vector128=mx.zeros((128,), dtype=mx.float32))):
                            positions, vectors, _task, _frontier, _policy = (
                                motif_read_impl._retained_motif_row(
                                    row, compiled.compiled.compiler_configs[0],
                                    compiled.sources[0], None, {},
                                    compiled.compiled.features, parent.extents,
                                    len(row.positions),
                                    compiled.compiled._projections[0]))
                    preparation_wall_seconds = time.perf_counter() - started

        self.assertEqual(len(prepared.compiled_rows), 4)
        self.assertEqual(
            prepared.training_batch.delivered_content_sha256,
            delivery.specimen_content_sha256)
        self.assertEqual(resource_plan.logical_row_ids, tuple(row["id"] for row in rows))
        self.assertEqual(len(positions), len(row.positions))
        self.assertEqual(vectors.shape, (len(row.positions), 128))
        self.assertLess(preparation_wall_seconds, 1.0)
        compiled = prepared.compiled_rows[0]
        self.assertIsNone(compiled.source_execution_authority)
        self.assertIsNone(compiled.training_authority)
        self.assertIsNone(compiled.task_authority)
        self.assertIsNotNone(compiled.visit_provenance)
        self.assertEqual(compiled.visit_provenance.capability_id, "B.AND")

    def test_learning_first_compiler_keeps_fresh_support_out_of_rehearsal_metadata(self):
        self.current, self.parent_graph = historical_school_release()
        snapshot = portable_atlas_snapshot()
        schema, features, atlas_selection = journey_source(snapshot)
        with wide_shape_patch(len(snapshot.abi_entries)):
            self.publish_matching_genesis(snapshot, schema, features)
            with self.journey_mounts(snapshot, schema, features, atlas_selection):
                parent, context, atlas_path, feature_path = _execution_context(self.run)
                direct = tuple(context.draw_rows(
                    seed=12345, capability="B.AND", each=4))
                support_pool = tuple(context.draw_rows(
                    seed=12346, capability="B.AND", each=4))
                direct_ids = {row["id"] for row in direct}
                support = next(row for row in support_pool if row["id"] not in direct_ids)
                rows = (*direct, support)
                execution = context.release.execution_plan.capability_map["B.AND"]
                delivery = describe_delivered_teaching(
                    context.release, "B.AND", execution.teaching_option_ids[0], direct)
                generation = execution_generation_digest(
                    parent.retained_state.optimizer.parameters,
                    spec=parent.topology, extents=parent.extents)
                with evidence_mode(strict=False):
                    prepared = prepare_factory_training_batch(
                        context, parent, atlas_path, feature_path, rows, generation,
                        capability="B.AND", delivery=delivery, requested_count=5,
                        source_seed=12345, source_each=4, optimizer_step_seed=7,
                        visit_provenance=visit_provenance("B.AND"),
                        teacher_strategy={"depth": 3},
                        fresh_support_by_id={support["id"]: "fresh_support"})

        metadata = tuple(row.provenance for row in prepared.training_batch.rows)
        self.assertTrue(all(item.rehearsal is None for item in metadata))
        self.assertTrue(all(item.auxiliary_role is None for item in metadata[:4]))
        self.assertEqual(metadata[4].row_id, support["id"])
        self.assertEqual(metadata[4].auxiliary_role, "fresh_support")
