"""Production-shaped proof for the authority-light BAMF source path."""
import time
import unittest
from unittest.mock import patch

from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_operator.session import _execution_context
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.factory_task_authority import factory_task_authority
from bilqis_mlx.runtime.factory_training_bridge import prepare_factory_training_batch
from bilqis_mlx.runtime.tests.batch.training.visit_provenance_support import visit_provenance

from .pre_neural_journey_support import (
    PreNeuralJourneySupport, historical_school_release, journey_source,
    portable_atlas_snapshot, wide_shape_patch,
)


class LearningFirstSourcePathTests(PreNeuralJourneySupport, unittest.TestCase):
    def test_factory_batch_has_no_source_or_training_authority_under_two_seconds(self):
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
                            side_effect=AssertionError("learning-first source redraw")):
                        prepared = prepare_factory_training_batch(
                            context, parent, atlas_path, feature_path, rows, generation,
                            capability="B.AND", delivery=delivery, requested_count=4,
                            source_seed=12345, source_each=4, optimizer_step_seed=7,
                            visit_provenance=visit_provenance("B.AND"),
                            teacher_strategy={"policy": "learning-first"},
                            selected_source_authority=selected_source_authority)
                    preparation_wall_seconds = time.perf_counter() - started

        self.assertEqual(len(prepared.compiled_rows), 4)
        self.assertLess(preparation_wall_seconds, 2.0)
        compiled = prepared.compiled_rows[0]
        self.assertIsNone(compiled.source_execution_authority)
        self.assertIsNone(compiled.training_authority)
        self.assertIsNotNone(compiled.visit_provenance)
        self.assertEqual(compiled.visit_provenance.capability_id, "B.AND")
        authority = factory_task_authority(
            context, compiled, generation_binding=generation)
        self.assertEqual(authority.generation_binding, generation)
        self.assertIsNone(authority.training_authority_sha256)
