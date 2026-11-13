import os
import unittest

from bilqis_mlx.factory.tests.events import test_atlas_integration as atlas_tests
from bilqis_mlx.source_adapters import event_frames


@unittest.skipUnless(
    os.environ.get("BILQIS_ATLAS_REAL_CORPUS"),
    "real pinned A01 corpus not supplied",
)
class RealAtlasEventIntegrationTests(atlas_tests.EventCandidateAtlasIntegrationTests):
    def test_atlas_adapter_proposes_three_real_source_qualified_successors(self):
        candidate, source_frontier, policy, selection, learned = self.real_atlas_fixture(
            os.environ["BILQIS_ATLAS_REAL_CORPUS"])
        self.assertEqual(candidate.census.atlas_bundle_id, selection.bundle_id)
        self.assertEqual(candidate.census.semantic_release, learned.semantic_release)
        self.assertEqual(len(candidate.source_eligible_concept_ids), 9307)
        self.assertEqual(len(candidate.census.obligations), 12351)
        for capability, spec in event_frames.SOURCE_SPECS.items():
            semantic_id = event_frames.atlas_semantic_id(capability)
            concept = next(
                item for item in candidate.census.concepts
                if item.semantic_id == semantic_id)
            self.assertIn(
                f"lexicon/lexicon_root_senses/{spec.sense_id}",
                concept.source_refs,
            )
        candidate = self.bounded_realization_candidate(candidate)
        self.assertEqual(len(candidate.source_eligible_concept_ids), 3)

        state = (self.current, self.parent_graph, {"A.IDENTITY"}, None, None)
        observed = []
        for capability in event_frames.SOURCE_SPECS:
            state = self._stage_capability(
                candidate, source_frontier, policy, state, capability)
            observed.append(capability)
        self.assertEqual(tuple(observed), tuple(event_frames.SOURCE_SPECS))
        self._assert_final_frontier(
            candidate,
            state,
            expected_status=atlas_tests.FrontierStatus.COMPLETE_ATLAS_COVERAGE,
            expected_uncovered=0,
        )


if __name__ == "__main__":
    unittest.main()
