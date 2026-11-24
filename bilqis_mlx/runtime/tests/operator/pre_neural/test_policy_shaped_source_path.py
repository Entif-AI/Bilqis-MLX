"""Native policy-shaped source subsets reach actual Factory batch preparation."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_operator.session import _execution_context
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.factory_candidate_components import _resource_plan
from bilqis_mlx.runtime.factory_training_bridge import prepare_factory_training_batch
from bilqis_mlx.runtime.priority_lesson import (
    prepare_lesson_pool, require_step_primary_lesson, shape_priority_lesson,
)
from bilqis_mlx.runtime.bamf_operator.source_prefetch import (
    CandidateSourceLane, SourcePrefetchMetrics,
)
from bilqis_mlx.runtime.accepted_priority_candidate_execution import _candidate_delivery_inputs
from bilqis_mlx.runtime.factory_candidate_training import FactoryDeliveryObservation
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.priority_source_offer import prepare_priority_source_offer
from bilqis_mlx.runtime.tests.batch.training.visit_provenance_support import visit_provenance

from .pre_neural_journey_support import (
    PreNeuralJourneySupport, historical_school_release, journey_source,
    portable_atlas_snapshot, wide_shape_patch,
)


class PolicyShapedSourcePathTests(PreNeuralJourneySupport, unittest.TestCase):
    def test_fresh_primary_lessons_preserve_policy_and_seed_across_prefetch(self):
        self.current, self.parent_graph = historical_school_release()
        snapshot = portable_atlas_snapshot()
        schema, features, atlas_selection = journey_source(snapshot)
        with wide_shape_patch(len(snapshot.abi_entries)):
            self.publish_matching_genesis(snapshot, schema, features)
            with self.journey_mounts(snapshot, schema, features, atlas_selection), evidence_mode(strict=False):
                parent, context, atlas_path, _ = _execution_context(self.run)
                offer = prepare_priority_source_offer(
                    context, parent, atlas_path, capability="B.AND",
                    source_seed=17, source_each=32)
                policy = {"depth": 3, "contrast": 0.5, "lr": 0.001}
                shaped, metadata = shape_priority_lesson(
                    context, parent, offer, prepare_lesson_pool(context, offer), policy)
                selection = SimpleNamespace(
                    offer=shaped, policy=policy, metadata={"primary_lesson": metadata},
                    visit=SimpleNamespace(identity=SimpleNamespace(visit_id="fixture:visit")))

                def lessons(workers, executor):
                    lane = CandidateSourceLane(
                        selection, context, parent, 3, workers=workers, executor=executor,
                        metrics=SourcePrefetchMetrics(), policy_support_enabled=True)
                    return tuple(lane.lesson(i) for i in (1, 2, 3))

                serial = lessons(0, None)
                with ThreadPoolExecutor(max_workers=2) as executor:
                    parallel = lessons(2, executor)
                self.assertEqual([x.direct for x in serial], [x.direct for x in parallel])
                self.assertEqual([x.source_seed for x in serial], [x.source_seed for x in parallel])
                self.assertEqual(len({x.source_seed for x in serial}), 3)
                self.assertEqual(len({tuple(row["id"] for row in x.direct) for x in serial}), 3)
                self.assertEqual(serial[0].direct, shaped.rows())
                capture = SimpleNamespace(attempt_id="fixture", selected_option="B.AND",
                                          delivery=lambda **_: None)
                for ordinal, lesson in enumerate(serial[1:], 2):
                    step = parent.retained_state.optimizer_step + ordinal
                    bound, controls = require_step_primary_lesson(
                        lesson.primary_lesson, context, selection, lesson.direct, step)
                    observation = FactoryDeliveryObservation(capture, step, lesson.direct, lesson.source_seed)
                    result = _candidate_delivery_inputs(
                        selection, context, lesson.direct, (), (), {}, {}, {}, observation,
                        prepared_primary_lesson=lesson.primary_lesson)
                    self.assertIs(result[0], bound)
                    self.assertEqual(result[-1].seed, lesson.source_seed)
                    self.assertEqual(result[-1].option_rows, lesson.direct)
                    self.assertEqual(result[-1].controls["depth_control"], controls["controls"]["depth_control"])
                    with self.assertRaises(BilqisError):
                        require_step_primary_lesson(
                            lesson.primary_lesson, context, selection, serial[0].direct, step)

    def test_policy_shaped_subset_reaches_compiled_batch_without_redraw(self):
        self.current, self.parent_graph = historical_school_release()
        snapshot = portable_atlas_snapshot()
        schema, features, atlas_selection = journey_source(snapshot)
        with wide_shape_patch(len(snapshot.abi_entries)):
            self.publish_matching_genesis(snapshot, schema, features)
            with self.journey_mounts(snapshot, schema, features, atlas_selection):
                capability = "B.AND"
                for strict in (False, True):
                    with self.subTest(strict=strict), evidence_mode(strict=strict):
                        parent, context, atlas_path, feature_path = _execution_context(self.run)
                        generation = execution_generation_digest(
                            parent.retained_state.optimizer.parameters,
                            spec=parent.topology, extents=parent.extents)
                        offer = prepare_priority_source_offer(
                            context, parent, atlas_path, capability=capability,
                            source_seed=17, source_each=32)
                        pool = prepare_lesson_pool(context, offer)
                        policy = {"depth": 3, "contrast": 0, "lr": 0.001}
                        shaped, metadata = shape_priority_lesson(
                            context, parent, offer, pool, policy)
                        rows = shaped.rows()
                        self.assertNotEqual(rows, offer.rows())
                        self.assertEqual(metadata["token_count"], 700)
                        execution = context.release.execution_plan.capability_map[capability]
                        delivery = describe_delivered_teaching(
                            context.release, capability, execution.teaching_option_ids[0], rows)
                        with patch.object(type(context), "bind_rows",
                                          side_effect=AssertionError("source redraw")):
                            prepared = prepare_factory_training_batch(
                                context, parent, atlas_path, feature_path, rows, generation,
                                capability=capability, delivery=delivery,
                                requested_count=len(rows), source_seed=17, source_each=len(rows),
                                optimizer_step_seed=7, visit_provenance=visit_provenance(capability),
                                teacher_strategy=policy,
                                selected_source_authority=shaped.source_authority)
                        plan, _ = _resource_plan(prepared, parent, None)
                        self.assertEqual(plan.logical_row_ids, tuple(row["id"] for row in rows))
                        self.assertEqual(tuple(row.provenance.row_id for row in prepared.training_batch.rows),
                                         tuple(row["id"] for row in rows))
                        self.assertEqual(prepared.training_batch.delivered_content_sha256,
                                         delivery.specimen_content_sha256)
