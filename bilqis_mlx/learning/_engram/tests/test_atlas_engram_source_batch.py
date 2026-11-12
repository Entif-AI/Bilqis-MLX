"""C08 logical-batch motif preparation preserves B07 source multiplicity."""
from __future__ import annotations

import os
from pathlib import Path
import unittest

from bilqis_mlx.learning.atlas_engram import MotifBudget, MotifManifest
from bilqis_mlx.learning.atlas_engram_source import (
    SourceQualifiedMotifRequest,
    _prepare_source_qualified_motif_batch_with_parent,
    source_qualified_motif_context,
)
from bilqis_mlx.learning.atlas_engram_transaction import (
    MotifAllocationSnapshot,
    _prepare_candidate_motif_snapshot,
)
from bilqis_mlx.learning._engram.tests.test_atlas_engram_source import (
    REAL_RELEASE,
    SourceQualifiedMotifTests,
)
from bilqis_mlx.semantics.context_eligibility import SourceFrontier


@unittest.skipUnless(
    os.environ.get("BILQIS_ATLAS_REAL_ARTIFACT"),
    "real repo-pinned A01 artifact supplied at source turn-in",
)
class SourceQualifiedMotifBatchTests(unittest.TestCase):
    def test_two_rows_prepare_one_multiplicity_preserving_candidate(self):
        fixture = SourceQualifiedMotifTests(
            "test_real_source_replay_qualifies_pinned_schema_and_owner_grants")
        (selection, source_root, graph, adapter, row, task, policy,
         seed, each, profile) = fixture._case()
        rows = tuple(adapter.draw(
            source_root=source_root, graph=graph, course=None,
            capability=row["capability"], seed=seed, each=each))
        self.assertEqual(len(rows), each)
        requests = tuple(SourceQualifiedMotifRequest(
            adapter, item, selection, Path(source_root), graph, task,
            SourceFrontier(1, 1, ()), policy, seed, each, profile, None,
        ) for item in rows)
        parent = MotifAllocationSnapshot(MotifManifest(REAL_RELEASE))
        budget = MotifBudget(64)
        approved, frontiers = _prepare_source_qualified_motif_batch_with_parent(
            requests, budget=budget, parent=parent)

        projections, qualified = [], []
        for request in requests:
            projection, row_inputs, _frontier = source_qualified_motif_context(
                request.source_adapter, request.row, request.atlas_selection,
                source_root=request.source_root, graph=request.graph,
                task_scope=request.task_scope,
                source_frontier=request.source_frontier, policy=request.policy,
                source_seed=request.source_seed, source_each=request.source_each,
                source_profile_parameters=request.source_profile_parameters,
                course=request.course)
            projections.append(projection)
            qualified.extend(row_inputs)
        expected = _prepare_candidate_motif_snapshot(
            tuple(qualified), parent, budget)

        self.assertEqual(approved.candidate, expected)
        self.assertEqual(len(frontiers), len(rows))
        self.assertTrue(all(frontier.grants for frontier in frontiers))
        self.assertNotIn(
            approved.approved_context_digest,
            tuple(projection.digest for projection in projections))


if __name__ == "__main__":
    unittest.main()
