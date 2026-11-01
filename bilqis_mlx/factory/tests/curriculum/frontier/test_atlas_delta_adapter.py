from dataclasses import replace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.atlas_frontier import (
    AtlasCoverageEpoch, AtlasLearnerEvidence, next_atlas_delta,
)
from bilqis_mlx.factory.atlas_frontier_progress import FrontierStatus, plan_frontier_progress
from bilqis_mlx.factory.atlas_frontier_selection import select_frontier_delta
from bilqis_mlx.factory.autonomy import compile_autonomy_plan, initial_evidence_ledger
from bilqis_mlx.factory.candidate_realizations import project_authoritative_target
from bilqis_mlx.factory.jit_curriculum import CurriculumDeltaProposal
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import rehash
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_progress import _stage
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_selection import (
    _candidate, _closure, _snapshot,
)
from bilqis_mlx.factory.tests.curriculum.frontier.test_candidate_staging import CandidateStagingFixture


class AtlasDeltaAdapterTests(unittest.TestCase):
    def setUp(self):
        staging = CandidateStagingFixture()
        staging.setUp()
        self.staging = staging
        self.staged = staging.stage()
        self.current = staging.current
        self.frontier = staging.frontier
        self.snapshot = rehash(
            _snapshot(self.current),
            candidate_frontier_sha256=self.frontier.release_sha256,
            staged_factory_release_sha256s=(self.staged.successor.release_sha256,),
        )
        self.closure = _closure(self.snapshot, tuple(
            _candidate(self.snapshot, identity)
            for identity in self.snapshot.source_eligible_concept_ids))
        self.plan = compile_autonomy_plan(self.current)
        self.learner = AtlasLearnerEvidence(
            initial_evidence_ledger(self.current, plan=self.plan), "e" * 64, 0)

    def _authority(self, semantic_id, current):
        if current.release_sha256 != self.current.release_sha256:
            raise ValueError
        if semantic_id == "z.op.0":
            return (self.staged.successor.transition.added_capabilities,
                    tuple(self.staged.successor.semantic_catalog[
                        len(self.current.semantic_catalog):]))
        suffix = semantic_id.rsplit(".", 1)[-1]
        return ((f"Z.N{suffix}",), (f"fixture.semantic.{suffix}",))

    def _epoch(self, **changes):
        values = dict(
            snapshot=self.snapshot, closure=self.closure,
            candidate_frontier=self.frontier, current_release=self.current,
            staged_candidates=(self.staged,), prior=None)
        values.update(changes)
        return AtlasCoverageEpoch(**values)

    def test_pure_selection_drives_existing_jit_binding_without_admission(self):
        with patch(
            "bilqis_mlx.factory.candidate_realizations.project_realized_target",
            side_effect=self._authority,
        ), patch(
            "bilqis_mlx.factory.atlas_frontier_progress_validation.project_realized_target",
            side_effect=self._authority,
        ), patch(
            "bilqis_mlx.factory.candidate_realizations.realized_source_sense_id",
            return_value=self.staged.source_sense_id,
        ):
            proposal = next_atlas_delta(self._epoch(), self.learner, self.plan)
        self.assertIsInstance(proposal, CurriculumDeltaProposal)
        self.assertEqual(proposal.selected_candidate_ids, (self.staged.candidate_id,))
        self.assertEqual(
            proposal.selected_successor_sha256, self.staged.successor.release_sha256)
        self.assertEqual(proposal.current_release_sha256, self.current.release_sha256)

    def test_unpersisted_staged_successor_is_rejected_before_jit(self):
        snapshot = rehash(self.snapshot, staged_factory_release_sha256s=())
        closure = _closure(snapshot, tuple(
            _candidate(snapshot, identity)
            for identity in snapshot.source_eligible_concept_ids))
        epoch = self._epoch(snapshot=snapshot, closure=closure)
        with self.assertRaises(BilqisError) as caught:
            next_atlas_delta(epoch, self.learner, self.plan)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PLANNER_ADAPTER_STAGED_SET_INVALID",
        )

    def test_ready_semantic_without_realized_staged_binding_is_explicit_debt(self):
        with patch(
            "bilqis_mlx.factory.candidate_realizations.project_realized_target",
            side_effect=self._authority,
        ), patch(
            "bilqis_mlx.factory.atlas_frontier_progress_validation.project_realized_target",
            side_effect=self._authority,
        ), patch(
            "bilqis_mlx.factory.candidate_realizations.realized_source_sense_id",
            return_value=self.staged.source_sense_id,
        ):
            result = next_atlas_delta(
                self._epoch(staged_candidates=()), self.learner, self.plan)
        self.assertIs(result, FrontierStatus.IMPLEMENTATION_UNCOVERED)

    def test_staged_restart_holds_same_successor_for_existing_admission_owner(self):
        with patch(
            "bilqis_mlx.factory.candidate_realizations.project_realized_target",
            side_effect=self._authority,
        ), patch(
            "bilqis_mlx.factory.atlas_frontier_progress_validation.project_realized_target",
            side_effect=self._authority,
        ), patch(
            "bilqis_mlx.factory.candidate_realizations.realized_source_sense_id",
            return_value=self.staged.source_sense_id,
        ):
            projections = tuple(
                project_authoritative_target(
                    identity, self.current,
                    tuple(row for row in self.closure.candidates
                          if row.semantic_id == identity))
                for identity in self.closure.constituent_order)
            selection = select_frontier_delta(
                self.snapshot, self.closure, self.current, projections)
            projection = next(
                item for item in projections
                if item.semantic_id == selection.selected_semantic_id)
            receipt = _stage(
                selection, projection, self.current, self.staged.successor, self.snapshot)
            prior = plan_frontier_progress(
                self.snapshot, self.closure, selection,
                current_release=self.current, selected_projection=projection,
                staged_receipt=receipt)
            result = next_atlas_delta(
                self._epoch(prior=prior), self.learner, self.plan)
        self.assertIs(result, FrontierStatus.LEASE_REQUIRED)
        self.assertEqual(
            prior.pending_staged_successor_sha256, self.staged.successor.release_sha256)


if __name__ == "__main__":
    unittest.main()
