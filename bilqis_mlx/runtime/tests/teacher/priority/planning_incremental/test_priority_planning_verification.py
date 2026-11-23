"""Process-live verification reuse for owner-derived A09 priority planning."""
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_operator.session import _execution_context
from bilqis_mlx.runtime.tests.operator.pre_neural.pre_neural_journey_support import (
    PreNeuralJourneySupport,
    historical_school_release,
    journey_source,
    portable_atlas_snapshot,
    wide_shape_patch,
)


class PriorityPlanningVerificationTests(PreNeuralJourneySupport, unittest.TestCase):
    def _planning_fixture(self):
        from bilqis_mlx.runtime.priority_planning_owner import (
            PriorityPlanningCache,
            build_priority_planning_epoch,
            priority_planning_from_epoch,
        )

        self.current, self.parent_graph = historical_school_release()
        snapshot = portable_atlas_snapshot()
        schema, features, atlas_selection = journey_source(snapshot)
        shape = wide_shape_patch(len(snapshot.abi_entries))
        shape.__enter__()
        self.addCleanup(shape.__exit__, None, None, None)
        self.publish_matching_genesis(snapshot, schema, features)
        mounts = self.journey_mounts(snapshot, schema, features, atlas_selection)
        mounts.__enter__()
        self.addCleanup(mounts.__exit__, None, None, None)
        _parent, context, atlas_path, _feature_path = _execution_context(self.run)
        cache = PriorityPlanningCache(self.run)
        epoch = build_priority_planning_epoch(
            self.run, context, atlas_path,
            authenticated_features=context._accepted_feature_context,
            planning_cache=cache,
        )
        planning = priority_planning_from_epoch(epoch, planning_cache=cache)
        self.assertIsNotNone(planning.selection)
        return context.release, planning

    def test_owner_verified_planning_skips_expensive_structural_revalidation(self):
        from bilqis_mlx.runtime import priority_qualification

        release, planning = self._planning_fixture()
        priority_qualification._verify_planning(planning, release, None)

        with patch.object(
                priority_qualification, "_planning",
                side_effect=AssertionError("full planning verification rerun")):
            priority_qualification._verify_planning(planning, release, None)

    def test_same_object_selection_mutation_invalidates_verified_planning(self):
        from bilqis_mlx.runtime import priority_qualification

        release, planning = self._planning_fixture()
        priority_qualification._verify_planning(planning, release, None)
        selection = planning.selection
        object.__setattr__(
            selection, "downstream_unlocks", selection.downstream_unlocks + 1)

        with self.assertRaises(BilqisError):
            priority_qualification._verify_planning(planning, release, None)

    def test_same_object_release_mutation_invalidates_verified_planning(self):
        from bilqis_mlx.runtime import priority_qualification

        release, planning = self._planning_fixture()
        priority_qualification._verify_planning(planning, release, None)
        object.__setattr__(release, "semantic_catalog_sha256", "9" * 64)

        with self.assertRaises((BilqisError, ValueError)):
            priority_qualification._verify_planning(planning, release, None)


if __name__ == "__main__":
    unittest.main()
