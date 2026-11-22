"""Cold-process reuse of non-authoritative A08 priority-planning derivation."""
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.bamf_operator.session import _execution_context
from bilqis_mlx.runtime.tests.operator.pre_neural.pre_neural_journey_support import (
    PreNeuralJourneySupport,
    historical_school_release,
    journey_source,
    portable_atlas_snapshot,
    wide_shape_patch,
)


class PriorityPlanningRestartMemoTests(PreNeuralJourneySupport, unittest.TestCase):
    def _fixture(self):
        from bilqis_mlx.runtime.priority_planning_owner import (
            PriorityPlanningCache,
            build_priority_planning_epoch,
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
        authenticated = context._accepted_feature_context
        first = build_priority_planning_epoch(
            self.run, context, atlas_path,
            authenticated_features=authenticated,
            planning_cache=PriorityPlanningCache(self.run),
        )
        return first, context, atlas_path, authenticated

    def test_new_process_cache_reuses_durable_semantic_curriculum(self):
        from bilqis_mlx.factory import skos_curriculum
        from bilqis_mlx.factory.skos_curriculum.serialization import _strict_source_bytes
        from bilqis_mlx.runtime.priority_planning_owner import (
            PriorityPlanningCache,
            build_priority_planning_epoch,
        )

        first, context, atlas_path, authenticated = self._fixture()
        with patch.object(
                skos_curriculum, "_compile_semantic_curriculum_snapshot",
                side_effect=AssertionError("cold restart recompiled semantic curriculum")):
            restarted = build_priority_planning_epoch(
                self.run, context, atlas_path,
                authenticated_features=authenticated,
                planning_cache=PriorityPlanningCache(self.run),
            )

        self.assertEqual(
            _strict_source_bytes(restarted.candidate_set),
            _strict_source_bytes(first.candidate_set),
        )
        self.assertEqual(restarted.snapshot.snapshot_sha256, first.snapshot.snapshot_sha256)
        self.assertEqual(restarted.closure.closure_sha256, first.closure.closure_sha256)

    def test_candidate_codec_round_trips_exact_canonical_bytes(self):
        from bilqis_mlx.factory.skos_curriculum.serialization import (
            _strict_source_bytes,
            curriculum_candidate_from_bytes,
        )

        first, _context, _atlas_path, _authenticated = self._fixture()
        raw = _strict_source_bytes(first.candidate_set)
        restored = curriculum_candidate_from_bytes(raw)
        self.assertEqual(_strict_source_bytes(restored), raw)

    def test_corrupt_memo_is_non_authoritative_and_recompiles(self):
        from bilqis_mlx.factory import skos_curriculum
        from bilqis_mlx.runtime.priority_planning_owner import (
            PriorityPlanningCache,
            build_priority_planning_epoch,
        )

        _first, context, atlas_path, authenticated = self._fixture()
        memo_files = tuple((self.run / "bamf-planning-derived" / "a08-candidate").glob("*.json"))
        self.assertEqual(len(memo_files), 1)
        memo_files[0].write_text('{"corrupt":true}\n', encoding="utf-8")
        original = skos_curriculum._compile_semantic_curriculum_snapshot
        with patch.object(
                skos_curriculum, "_compile_semantic_curriculum_snapshot",
                wraps=original) as compile_candidate:
            build_priority_planning_epoch(
                self.run, context, atlas_path,
                authenticated_features=authenticated,
                planning_cache=PriorityPlanningCache(self.run),
            )
        self.assertEqual(compile_candidate.call_count, 1)


if __name__ == "__main__":
    unittest.main()
