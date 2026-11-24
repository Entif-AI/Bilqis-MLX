"""Exercise the real accepted-context/session ownership of prepared problem routes."""
import unittest

from bilqis_mlx.data_plane import close_data_planes
from bilqis_mlx.runtime.bamf_operator.session import _SessionExecutionContext, _execution_context
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.factory_candidate_microbatch import prepare_learning_first_task_route
from bilqis_mlx.runtime.factory_training_bridge import LearningFirstPreparationCache

from .pre_neural_journey_support import (
    PreNeuralJourneySupport, historical_school_release, journey_source,
    portable_atlas_snapshot, wide_shape_patch,
)


def _routes(context, rows):
    features = context._accepted_feature_context
    cache = LearningFirstPreparationCache()
    cache.bind(context, features)
    routes = tuple(prepare_learning_first_task_route(
        context, row, features.features.semantic_release, cache=cache) for row in rows)
    return routes, cache


class PreparedTaskCatalogSessionTests(PreNeuralJourneySupport, unittest.TestCase):
    def test_reuse_across_accepted_publication_and_normal_restart(self):
        self.current, self.parent_graph = historical_school_release()
        snapshot = portable_atlas_snapshot()
        schema, features, selection = journey_source(snapshot)
        with wide_shape_patch(len(snapshot.abi_entries)):
            self.publish_matching_genesis(snapshot, schema, features)
            pointer = (self.run / "bamf-state.json").read_bytes()
            with self.journey_mounts(snapshot, schema, features, selection), evidence_mode(strict=False):
                session = _SessionExecutionContext(strict=False, loader=_execution_context)
                first = session(self.run)[1]
                rows = first.draw_rows(seed=12345, capability="B.AND", each=4)
                routes, initial = _routes(first, rows)
                self.assertEqual(initial.task_misses, len(rows))
                catalog = session.prepared_tasks
                session.accepted_publication()
                self.assertIsNone(session.snapshot)
                second = session(self.run)[1]
                self.assertIs(session.prepared_tasks, catalog)
                repeated, warm = _routes(second, rows)
                self.assertEqual(warm.task_hits, len(rows))
                self.assertTrue(all(a is b for a, b in zip(routes, repeated, strict=True)))
                session.persist_tasks()
                self.assertIsNotNone(catalog.plane.get_object_reference(catalog.reference))
                close_data_planes()
                restarted = _SessionExecutionContext(strict=False, loader=_execution_context)
                third = restarted(self.run)[1]
                restored, cold = _routes(third, rows)
                self.assertIsNot(restarted.prepared_tasks.routes, catalog.routes)
                self.assertEqual(cold.task_hits, len(rows))
                self.assertEqual(cold.task_misses, 0)
                self.assertEqual(restored, routes)
            self.assertEqual((self.run / "bamf-state.json").read_bytes(), pointer)
