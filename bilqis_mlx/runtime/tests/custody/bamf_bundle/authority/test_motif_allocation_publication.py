"""B07 allocation crosses C05/B13 publication and cold accepted custody."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from bilqis_mlx.learning._engram.tests.motif_fixtures import source
from bilqis_mlx.learning._retention.tests.motif_allocation_support import (
    CandidateMotifAllocationFixture, MOTIF,
)
from bilqis_mlx.learning.atlas_engram import MotifBudget
from bilqis_mlx.learning.atlas_engram_source import _issue_approved_motif_candidate
from bilqis_mlx.learning.atlas_engram_transaction import _prepare_candidate_motif_snapshot
from bilqis_mlx.learning.atlas_candidate import resolve_candidate
from bilqis_mlx.learning.atlas_retention_decision import issue_factory_retention_decision
from bilqis_mlx.runtime.bamf_bundle.admission import (
    accept_and_publish, derive_motif_successor_bundle, load_accepted_generation,
)
from bilqis_mlx.runtime.bamf_bundle.source_continuation import (
    _issue_continuation, stage_source_qualified_motif_allocation,
)
import bilqis_mlx.runtime.factory_retention_owner as retention_owner
from bilqis_mlx.runtime.factory_retention_owner import evaluate_factory_retention_candidate
from bilqis_mlx.runtime.capability_retention import Decision, DecisionStatus
from bilqis_mlx.runtime.tests.custody.bamf_bundle import helpers
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import publish_genesis, shape_patch


TARGET = "B07.MOTIF"


def _matching_source():
    item = source()
    frame = replace(item.frame, bindings=tuple(
        replace(binding, concept=replace(binding.concept, semantic_release="d" * 64))
        for binding in item.frame.bindings))
    return replace(item, frame=frame)


def _accepted_c05_decision(run_dir, transaction, parent, successor, retained):
    release_sha = "1" * 64
    capability = SimpleNamespace(capability_id=TARGET, grade_id="B")
    release = SimpleNamespace(
        release_sha256=release_sha,
        execution_plan=SimpleNamespace(
            capabilities=(capability,), capability_map={TARGET: capability}))
    source_context = SimpleNamespace(
        __post_init__=lambda: None, release=release,
        require_accepted_runtime=Mock())
    fixed = SimpleNamespace(rows=({"id": "fixed"},), seed=7)
    eligible = Decision(
        DecisionStatus.ELIGIBLE, "PAIRED_SCREEN_WITHIN_BUDGET",
        "a" * 64, "b" * 64, "c" * 64, "d" * 64)
    original = transaction.training_authorities
    object.__setattr__(transaction, "training_authorities", (
        SimpleNamespace(delivery_capability=TARGET, release_sha256=release_sha),))
    try:
        with patch.multiple(
                retention_owner, create=True,
                _training_exclusions=Mock(return_value=((), ())),
                _candidate_from_live_parent=Mock(
                    return_value=(parent, successor, retained, object())),
                read_current=Mock(return_value={"factory_release_sha256": release_sha}),
                frontier_exam=Mock(return_value={"factory_release_sha256": release_sha}),
                load_frontier_cohort=Mock(return_value=fixed),
                _instruments=Mock(return_value=(SimpleNamespace(case=SimpleNamespace()),)),
                case_census_digest=Mock(return_value="e" * 64),
                _cohort=Mock(return_value=object()),
                FoundationRetentionPolicy=Mock(return_value=object()),
                factory_complete_solver=Mock(side_effect=((object(), "b" * 64),
                                                          (object(), "c" * 64))),
                evaluate_foundation_fixed_school_candidate=Mock(return_value=eligible)):
            evaluation = evaluate_factory_retention_candidate(
                source_context, transaction, "artifact", TARGET, run_dir=run_dir)
    finally:
        object.__setattr__(transaction, "training_authorities", original)
    return issue_factory_retention_decision(evaluation)


class MotifAllocationPublicationTests(unittest.TestCase):
    def test_v6_publication_cold_load_preserves_motif_allocation_and_optimizer(self):
        fixture = CandidateMotifAllocationFixture()
        fixture.setUp()
        with TemporaryDirectory() as directory:
            run_dir = Path(directory)
            with (patch.dict(os.environ, {
                    "BILQIS_DATA_PLANE": str(run_dir / "plane.sqlite3")}),
                  patch.object(helpers, "DECLARED", fixture.declared),
                  shape_patch()):
                genesis = publish_genesis(run_dir)
                parent = load_accepted_generation(run_dir)
                fixture.parent = parent.retained_state
                fixture.extents = parent.extents
                transaction = fixture._step()
                proposal = _prepare_candidate_motif_snapshot(
                    (_matching_source(),), parent.retained_state.allocations,
                    MotifBudget(2))
                approved = _issue_approved_motif_candidate("e" * 64, proposal)
                continuation = _issue_continuation(
                    approved, parent, genesis["manifest_sha256"])
                staged = stage_source_qualified_motif_allocation(
                    run_dir, transaction, continuation)
                retained = resolve_candidate(staged, accepted=True)
                successor = derive_motif_successor_bundle(
                    parent, staged,
                    parent_manifest_sha256=genesis["manifest_sha256"],
                    delivery_events=({
                        "event": "BAMF_GENERATION_ACCEPTED",
                        "optimizer_step": retained.optimizer_step,
                    },))
                decision = _accepted_c05_decision(
                    run_dir, staged, parent, successor, retained)
                published = accept_and_publish(
                    run_dir, successor, retained, decision=decision,
                    feature_sha256=successor.extents.factor_map_digest,
                    reserve_gib=0., training_authorities=None)
                cold = load_accepted_generation(run_dir)

        self.assertEqual(cold.generation, 1)
        self.assertEqual(cold.transition["kind"], "MOTIF_ALLOCATION")
        self.assertEqual(cold.extents, successor.extents)
        self.assertEqual(cold.retained_state.allocations, retained.allocations)
        self.assertEqual(published["manifest_sha256"],
                         cold.retained_state.custody.manifest_sha256)
        for tree in ("parameters", "m", "v", "update_counts"):
            np.testing.assert_array_equal(
                np.asarray(getattr(cold.retained_state.optimizer, tree)[MOTIF]),
                np.asarray(getattr(retained.optimizer, tree)[MOTIF]))


if __name__ == "__main__":
    unittest.main()
