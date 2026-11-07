from dataclasses import replace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.atlas_frontier import (
    AtlasCoverageEpoch, AtlasLearnerEvidence, next_atlas_delta,
    staged_selection_receipt,
)
from bilqis_mlx.factory.atlas_delta_adapter import (
    _credited_requested_keys,
)
from bilqis_mlx.factory.atlas_frontier_progress import FrontierStatus, plan_frontier_progress
from bilqis_mlx.factory.atlas_frontier_closure import ClosureReason, ClosureStatus
from bilqis_mlx.factory.atlas_frontier_selection import select_frontier_delta
from bilqis_mlx.factory.autonomy import compile_autonomy_plan, initial_evidence_ledger
from bilqis_mlx.factory.candidate_realizations import project_authoritative_target
from bilqis_mlx.factory.jit_curriculum import CurriculumDeltaProposal
from bilqis_mlx.factory.skos_curriculum import IMPLEMENTATION_UNCOVERED
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

    def test_lower_ranked_unrealized_semantic_does_not_starve_realized_winner(self):
        calls = []

        def winner_only(semantic_id, current):
            calls.append(semantic_id)
            if semantic_id != "z.op.0":
                raise ValueError
            return self._authority(semantic_id, current)

        with patch(
            "bilqis_mlx.factory.candidate_realizations.project_realized_target",
            side_effect=winner_only,
        ), patch(
            "bilqis_mlx.factory.atlas_frontier_progress_validation.project_realized_target",
            side_effect=self._authority,
        ), patch(
            "bilqis_mlx.factory.candidate_realizations.realized_source_sense_id",
            return_value=self.staged.source_sense_id,
        ):
            proposal = next_atlas_delta(self._epoch(), self.learner, self.plan)
        self.assertIsInstance(proposal, CurriculumDeltaProposal)
        self.assertEqual(calls, ["z.op.0"])

    def test_missing_winner_realization_returns_typed_implementation_debt(self):
        with patch(
            "bilqis_mlx.factory.candidate_realizations.project_realized_target",
            side_effect=ValueError,
        ):
            result = next_atlas_delta(self._epoch(), self.learner, self.plan)
        self.assertIs(result, FrontierStatus.IMPLEMENTATION_UNCOVERED)

    def test_staged_receipt_rejects_self_consistent_wrong_comparator_metrics(self):
        with patch(
            "bilqis_mlx.factory.candidate_realizations.project_realized_target",
            side_effect=self._authority,
        ), patch(
            "bilqis_mlx.factory.atlas_frontier_progress_validation.project_realized_target",
            side_effect=self._authority,
        ):
            rows = tuple(
                row for row in self.closure.candidates if row.semantic_id == "z.op.0")
            projection = project_authoritative_target("z.op.0", self.current, rows)
            selection = select_frontier_delta(
                self.snapshot, self.closure, self.current, tuple(
                    project_authoritative_target(
                        identity, self.current, tuple(
                            row for row in self.closure.candidates
                            if row.semantic_id == identity))
                    for identity in self.closure.constituent_order))
            forged = replace(selection, prerequisite_slope=999, selection_sha256="0" * 64)
            forged = replace(forged, selection_sha256=forged.expected_digest())
            with self.assertRaises(BilqisError) as caught:
                staged_selection_receipt(self._epoch(), forged, projection, self.staged)
        self.assertEqual(caught.exception.context["reason"], "BAMF_PLANNER_SELECTION_INVALID")

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

    def test_invalidated_historical_receipt_does_not_suppress_replanning(self):
        with patch(
            "bilqis_mlx.factory.candidate_realizations.project_realized_target",
            side_effect=self._authority,
        ), patch(
            "bilqis_mlx.factory.atlas_frontier_progress_validation.project_realized_target",
            side_effect=self._authority,
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
        corrected_rows = tuple(
            replace(row, implementation_status=IMPLEMENTATION_UNCOVERED)
            if row.semantic_id == selection.selected_semantic_id else row
            for row in self.snapshot.coverage_rows
        )
        corrected = rehash(
            self.snapshot,
            coverage_rows=corrected_rows,
            event_generation=self.snapshot.event_generation + 1,
            predecessor_sha256=self.snapshot.snapshot_sha256,
        )
        invalidated_reason = ClosureReason(
            "FAMILY_IMPLEMENTATION_UNCOVERED",
            "family:positive_identity",
        )
        dependent_reason = ClosureReason(
            "PREREQUISITE_IMPLEMENTATION_UNCOVERED",
            "factory:prerequisite",
            selection.selected_semantic_id,
        )
        corrected_closure = _closure(corrected, tuple(
            _candidate(
                corrected,
                identity,
                status=(
                    ClosureStatus.IMPLEMENTATION_UNCOVERED
                    if identity in {selection.selected_semantic_id, "z.op.1"}
                    else ClosureStatus.READY
                ),
                reasons=(
                    (invalidated_reason,)
                    if identity == selection.selected_semantic_id
                    else ((dependent_reason,) if identity == "z.op.1" else ())
                ),
            )
            for identity in corrected.source_eligible_concept_ids
        ))
        with patch(
            "bilqis_mlx.factory.atlas_frontier_progress_validation.project_realized_target",
            side_effect=self._authority,
        ):
            invalidated = plan_frontier_progress(
                corrected, corrected_closure, prior=prior)
            self.assertIs(invalidated.status, FrontierStatus.REPLAN_REQUIRED)
            self.assertIsNone(invalidated.pending_staged_receipt_sha256)
            self.assertEqual(invalidated.staged_receipts, prior.staged_receipts)
            epoch = self._epoch(
                snapshot=corrected,
                closure=corrected_closure,
                prior=invalidated,
            )
            self.assertEqual(_credited_requested_keys(epoch), ())


if __name__ == "__main__":
    unittest.main()
