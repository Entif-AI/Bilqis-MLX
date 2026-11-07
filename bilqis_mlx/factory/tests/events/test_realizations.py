import hashlib
import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory import candidate_realizations
from bilqis_mlx.factory.tests.events.support import (
    EventCandidateRealizationFixture,
    LEGACY,
)
from bilqis_mlx.source_adapters import event_frames


class EventCandidateRealizationTests(EventCandidateRealizationFixture, unittest.TestCase):
    def test_three_source_qualified_event_successors_stage_successively(self):
        current = self.current
        graph = self.parent_graph
        observed = []
        for index, capability in enumerate(event_frames.SOURCE_SPECS):
            staged = candidate_realizations.prepare_realized_candidate(
                self.frontier, current, graph, event_frames.atlas_semantic_id(capability),
                source_root=LEGACY, source_registry=self.source_registry,
                answer_registry=self.answer_registry,
            )
            self.assertEqual(staged.source_sense_id,
                             event_frames.SOURCE_SPECS[capability].sense_id)
            self.assertEqual(staged.successor.transition.added_capabilities, (capability,))
            expected = (event_frames.SYMBOLS[capability],)
            if index == 0:
                from bilqis_mlx.source_adapters import copular_curriculum
                expected = (copular_curriculum.PROJECTION_ADMISSION_TOKEN, *expected)
            self.assertEqual(
                staged.successor.semantic_catalog[len(current.semantic_catalog):], expected)
            graph = candidate_realizations.admitted_candidate_graph(staged, graph)
            current = staged.successor
            observed.append(capability)
        self.assertEqual(tuple(observed), tuple(event_frames.SOURCE_SPECS))

    def test_each_successive_event_stage_restarts_as_the_same_candidate(self):
        from bilqis_mlx.runtime.candidate_staging import (
            load_staged_candidates, persist_staged_candidate,
        )

        current = self.current
        graph = self.parent_graph
        for capability in event_frames.SOURCE_SPECS:
            staged = candidate_realizations.prepare_realized_candidate(
                self.frontier, current, graph, event_frames.atlas_semantic_id(capability),
                source_root=LEGACY, source_registry=self.source_registry,
                answer_registry=self.answer_registry,
            )
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                persist_staged_candidate(root, staged, self.frontier, current)
                self.assertEqual(load_staged_candidates(root, self.frontier, current), (staged,))
            graph = candidate_realizations.admitted_candidate_graph(staged, graph)
            current = staged.successor

    def test_event_atlas_projection_and_source_identity_share_one_owner(self):
        current = self.current
        graph = self.parent_graph
        for index, capability in enumerate(event_frames.SOURCE_SPECS):
            semantic_id = event_frames.atlas_semantic_id(capability)
            added, identities = candidate_realizations.project_realized_target(
                semantic_id, current)
            self.assertEqual(added, (capability,))
            expected = (event_frames.SYMBOLS[capability],)
            if index == 0:
                from bilqis_mlx.source_adapters import copular_curriculum
                expected = (copular_curriculum.PROJECTION_ADMISSION_TOKEN, *expected)
            self.assertEqual(identities, expected)
            self.assertEqual(
                candidate_realizations.realized_source_sense_id(semantic_id),
                event_frames.SOURCE_SPECS[capability].sense_id,
            )
            staged = candidate_realizations.prepare_realized_candidate(
                self.frontier, current, graph, semantic_id,
                source_root=LEGACY, source_registry=self.source_registry,
                answer_registry=self.answer_registry,
            )
            self.assertEqual(
                staged.successor.semantic_catalog[len(current.semantic_catalog):], identities)
            graph = candidate_realizations.admitted_candidate_graph(staged, graph)
            current = staged.successor

    def test_foreign_same_name_event_row_cannot_be_reused_as_source_authority(self):
        graph = event_frames.projected_graph(self.parent_graph, ("D.EVENT_OCCURRENCE",))
        token = event_frames.SYMBOLS["D.EVENT_OCCURRENCE"]
        index = graph["tokens"].index(token)
        foreign = dict(graph["nodes"][index], semantic_id="foreign:event-occurrence")
        graph["nodes"][index] = foreign
        graph["row_contract_sha256"][token] = hashlib.sha256(json.dumps(
            foreign, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False).encode()).hexdigest()
        with self.assertRaises(BilqisError):
            event_frames.projected_graph(graph, ("D.EVENT_OCCURRENCE",))

    def test_frontier_source_order_does_not_change_event_successor(self):
        semantic_id = event_frames.atlas_semantic_id("D.EVENT_OCCURRENCE")
        expected = candidate_realizations.prepare_realized_candidate(
            self.frontier, self.current, self.parent_graph, semantic_id,
            source_root=LEGACY, source_registry=self.source_registry,
            answer_registry=self.answer_registry,
        )
        reversed_frontier = replace(
            self.frontier, candidates=tuple(reversed(self.frontier.candidates)))
        reversed_frontier = replace(
            reversed_frontier, release_sha256=reversed_frontier.expected_digest())
        observed = candidate_realizations.prepare_realized_candidate(
            reversed_frontier, self.current, self.parent_graph, semantic_id,
            source_root=LEGACY, source_registry=self.source_registry,
            answer_registry=self.answer_registry,
        )
        self.assertEqual(observed.candidate_id, expected.candidate_id)
        self.assertEqual(observed.successor, expected.successor)

    def test_event_staging_rejects_rehashed_frontier_source_digest(self):
        capability = "D.EVENT_OCCURRENCE"
        sense_id = event_frames.SOURCE_SPECS[capability].sense_id
        senses = tuple(
            replace(item, source_text_sha256="0" * 64)
            if item.sense_id == sense_id else item
            for item in self.frontier.senses
        )
        forged = replace(self.frontier, senses=senses, release_sha256="0" * 64)
        forged = replace(forged, release_sha256=forged.expected_digest())
        with self.assertRaises(BilqisError) as failure:
            candidate_realizations.prepare_realized_candidate(
                forged, self.current, self.parent_graph,
                event_frames.atlas_semantic_id(capability),
                source_root=LEGACY, source_registry=self.source_registry,
                answer_registry=self.answer_registry,
            )
        self.assertEqual(
            failure.exception.context["reason"],
            "EVENT_FRAME_FRONTIER_SOURCE_AUTHORITY_DRIFT",
        )


if __name__ == "__main__":
    unittest.main()
