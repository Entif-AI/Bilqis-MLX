"""Production-shaped neural-inert proof for #1537 selected-source reuse."""
import unittest

from scripts.bamf.profiling.source_materialization_reuse_profile import profile

from .pre_neural_journey_support import (
    PreNeuralJourneySupport, historical_school_release, journey_source,
    portable_atlas_snapshot, wide_shape_patch,
)


class SourceMaterializationReuseTests(PreNeuralJourneySupport, unittest.TestCase):
    def test_exact_warm_selected_source_handoff_is_under_two_seconds(self):
        self.current, self.parent_graph = historical_school_release()
        snapshot = portable_atlas_snapshot()
        schema, features, selection = journey_source(snapshot)
        with wide_shape_patch(len(snapshot.abi_entries)):
            self.publish_matching_genesis(snapshot, schema, features)
            (self.run / ".issue1537-disposable-profile").touch()
            with self.journey_mounts(snapshot, schema, features, selection):
                result = profile(self.run, repeats=3, max_warm_seconds=2.0)

        self.assertTrue(result["stable_identity"])
        self.assertTrue(result["gate_passed"])
        self.assertTrue(all(sample["cache_hit"] for sample in result["samples"][1:]))
        self.assertLessEqual(max(result["warm_seconds"]), 2.0)
        self.assertEqual(result["samples"][0]["cache"]["misses"], 1)
        self.assertEqual(result["samples"][-1]["cache"]["hits"], 2)
        self.assertTrue(all(
            sample["stages"]["source_materialization_wait_wall_seconds"] == 0.0
            for sample in result["samples"]))
        self.assertTrue(all(
            sample["source_preparation_counts"]["source_context_builds"] == 0
            for sample in result["samples"][1:]))
        self.assertTrue(all(
            sample["source_preparation_counts"]["compiled_source_builds"] == 0
            for sample in result["samples"][1:]))
        self.assertTrue(all(
            sample["atlas_reload_count"] == 1 for sample in result["samples"]))


if __name__ == "__main__":
    unittest.main()
