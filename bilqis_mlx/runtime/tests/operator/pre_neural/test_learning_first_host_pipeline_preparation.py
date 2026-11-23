"""Issue #1577 learning-first ahead-preparation parity and invalidation proof."""
from dataclasses import replace
import importlib
import unittest
from unittest.mock import patch

from bilqis_mlx.factory.teaching import content_digest, describe_delivered_teaching
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_operator.session import _execution_context
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.factory_training_bridge import (
    LearningFirstPreparationCache,
    prepare_factory_training_batch,
)
from bilqis_mlx.runtime.factory_training_preparation import (
    _prepared_ahead_matches,
    prepare_learning_first_source_inputs_ahead,
)
from bilqis_mlx.runtime.tests.batch.training.visit_provenance_support import visit_provenance

from .pre_neural_journey_support import (
    PreNeuralJourneySupport,
    historical_school_release,
    journey_source,
    portable_atlas_snapshot,
    wide_shape_patch,
)


class LearningFirstHostPipelinePreparationTests(
        PreNeuralJourneySupport, unittest.TestCase):

    def _case(self):
        self.current, self.parent_graph = historical_school_release()
        snapshot = portable_atlas_snapshot()
        schema, features, atlas_selection = journey_source(snapshot)
        self._shape = wide_shape_patch(len(snapshot.abi_entries))
        self._shape.__enter__()
        self.addCleanup(self._shape.__exit__, None, None, None)
        self.publish_matching_genesis(snapshot, schema, features)
        mounts = self.journey_mounts(snapshot, schema, features, atlas_selection)
        mounts.__enter__()
        self.addCleanup(mounts.__exit__, None, None, None)
        parent, context, atlas_path, feature_path = _execution_context(self.run)
        rows = tuple(context.draw_rows(seed=12345, capability="B.AND", each=4))
        execution = context.release.execution_plan.capability_map["B.AND"]
        delivery = describe_delivered_teaching(
            context.release, "B.AND", execution.teaching_option_ids[0], rows)
        generation = execution_generation_digest(
            parent.retained_state.optimizer.parameters,
            spec=parent.topology, extents=parent.extents)
        return parent, context, atlas_path, feature_path, rows, delivery, generation

    def test_ahead_preparation_never_issues_future_step_authority(self):
        _parent, context, _atlas_path, _feature_path, rows, _delivery, _generation = (
            self._case())
        authority = importlib.import_module(
            "bilqis_mlx.runtime.candidate.step_authority")
        before = authority.learning_first_step_authority_metrics_snapshot()
        with evidence_mode(strict=False):
            ahead = prepare_learning_first_source_inputs_ahead(
                context, context._accepted_feature_context, rows,
                source_seed=12345, source_each=4)
        after = authority.learning_first_step_authority_metrics_snapshot()

        self.assertEqual(ahead.rows_sha256, content_digest(rows))
        self.assertEqual(before, after)

    def test_prepared_ahead_inputs_match_synchronous_learning_first_batch(self):
        parent, context, atlas_path, feature_path, rows, delivery, generation = self._case()
        with evidence_mode(strict=False):
            ahead = prepare_learning_first_source_inputs_ahead(
                context, context._accepted_feature_context, rows,
                source_seed=12345, source_each=4)
            control = prepare_factory_training_batch(
                context, parent, atlas_path, feature_path, rows, generation,
                capability="B.AND", delivery=delivery, requested_count=4,
                source_seed=12345, source_each=4, optimizer_step_seed=7,
                visit_provenance=visit_provenance("B.AND"),
                teacher_strategy={"policy": "learning-first"},
                learning_first_cache=LearningFirstPreparationCache())
            pipelined = prepare_factory_training_batch(
                context, parent, atlas_path, feature_path, rows, generation,
                capability="B.AND", delivery=delivery, requested_count=4,
                source_seed=12345, source_each=4, optimizer_step_seed=7,
                visit_provenance=visit_provenance("B.AND"),
                teacher_strategy={"policy": "learning-first"},
                learning_first_cache=LearningFirstPreparationCache(),
                prepared_learning_first_source_inputs=ahead)

        self.assertEqual(control.training_batch.authority_digest,
                         pipelined.training_batch.authority_digest)
        self.assertEqual(control.training_batch.delivered_content_sha256,
                         pipelined.training_batch.delivered_content_sha256)
        self.assertEqual(
            tuple(row.provenance for row in control.training_batch.rows),
            tuple(row.provenance for row in pipelined.training_batch.rows))
        self.assertEqual(
            tuple(row.model_input.eligibility_digest for row in control.training_batch.rows),
            tuple(row.model_input.eligibility_digest for row in pipelined.training_batch.rows))
        self.assertEqual(
            pipelined._performance_observation["pipeline_prepared_ahead_used"], 1)
        self.assertEqual(
            pipelined._performance_observation["pipeline_discarded_prefetch_work"], 0)

    def test_validated_source_packet_identity_skips_downstream_content_rehash(self):
        _parent, context, _atlas_path, _feature_path, rows, _delivery, _generation = (
            self._case())
        source_identity = "a" * 64
        with evidence_mode(strict=False):
            ahead = prepare_learning_first_source_inputs_ahead(
                context, context._accepted_feature_context, rows,
                source_seed=12345, source_each=4,
                source_identity=source_identity)
            with patch(
                    "bilqis_mlx.runtime.factory_training_preparation.content_digest",
                    side_effect=AssertionError("validated packet was rehashed")):
                self.assertTrue(_prepared_ahead_matches(
                    ahead, context, context._accepted_feature_context, rows,
                    source_seed=12345, source_each=4,
                    source_identity=source_identity))

    def test_identity_drift_discards_and_recomputes_exactly(self):
        parent, context, atlas_path, feature_path, rows, delivery, generation = self._case()
        with evidence_mode(strict=False):
            ahead = prepare_learning_first_source_inputs_ahead(
                context, context._accepted_feature_context, rows,
                source_seed=12345, source_each=4)
            tampered = replace(ahead, identity="f" * 64)
            control = prepare_factory_training_batch(
                context, parent, atlas_path, feature_path, rows, generation,
                capability="B.AND", delivery=delivery, requested_count=4,
                source_seed=12345, source_each=4, optimizer_step_seed=7,
                visit_provenance=visit_provenance("B.AND"),
                teacher_strategy={"policy": "learning-first"})
            recovered = prepare_factory_training_batch(
                context, parent, atlas_path, feature_path, rows, generation,
                capability="B.AND", delivery=delivery, requested_count=4,
                source_seed=12345, source_each=4, optimizer_step_seed=7,
                visit_provenance=visit_provenance("B.AND"),
                teacher_strategy={"policy": "learning-first"},
                prepared_learning_first_source_inputs=tampered)

        self.assertEqual(control.training_batch.authority_digest,
                         recovered.training_batch.authority_digest)
        self.assertEqual(
            recovered._performance_observation["pipeline_prepared_ahead_used"], 0)
        self.assertEqual(
            recovered._performance_observation["pipeline_discarded_prefetch_work"], 1)
