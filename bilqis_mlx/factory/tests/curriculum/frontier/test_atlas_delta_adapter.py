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
from bilqis_mlx.factory.atlas_delta_scope import AtlasDeltaScopeHandoff
from bilqis_mlx.factory.atlas_frontier_progress import FrontierStatus, plan_frontier_progress
from bilqis_mlx.factory.atlas_frontier_closure import ClosureReason, ClosureStatus
from bilqis_mlx.factory.atlas_frontier_selection import select_frontier_delta
from bilqis_mlx.factory.candidate_realizations import project_authoritative_target
from bilqis_mlx.factory.jit_curriculum import CurriculumDeltaProposal
from bilqis_mlx.factory.skos_curriculum import IMPLEMENTATION_UNCOVERED
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_delta_adapter_fixtures import (
    AtlasDeltaAdapterFixture,
)
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import rehash
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_progress import _stage
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_selection import (
    _candidate, _closure, _snapshot,
)


class AtlasDeltaAdapterTests(AtlasDeltaAdapterFixture):

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
            handoff = next_atlas_delta(self._epoch(), self.learner, self.plan)
        self.assertIsInstance(handoff, AtlasDeltaScopeHandoff)
        proposal = handoff.proposal
        handoff.verify()
        self.assertEqual(proposal.selected_candidate_ids, (self.staged.candidate_id,))
        self.assertEqual(
            proposal.selected_successor_sha256, self.staged.successor.release_sha256)
        self.assertEqual(proposal.current_release_sha256, self.current.release_sha256)

    def test_handoff_rejects_self_consistent_candidate_family_and_operator_substitution(self):
        handoff = self._handoff()
        forged_candidate = replace(
            handoff.staged_candidate,
            candidate_id="candidate-forged",
            staged_sha256="0" * 64,
        )
        forged_candidate = replace(
            forged_candidate, staged_sha256=forged_candidate.expected_digest())
        forged_sense = replace(
            handoff.staged_candidate,
            source_sense_id="sense:forged",
            staged_sha256="0" * 64,
        )
        forged_sense = replace(
            forged_sense, staged_sha256=forged_sense.expected_digest())
        forged_anchor = replace(
            handoff.staged_candidate,
            source_anchor="source:forged",
            staged_sha256="0" * 64,
        )
        forged_anchor = replace(
            forged_anchor, staged_sha256=forged_anchor.expected_digest())
        relabeled_candidate = replace(
            handoff.staged_candidate,
            candidate_id="candidate-forged",
            staged_sha256="0" * 64,
        )
        relabeled_candidate = replace(
            relabeled_candidate,
            staged_sha256=relabeled_candidate.expected_digest(),
        )
        relabeled_proposal = replace(
            handoff.proposal,
            selected_candidate_ids=(relabeled_candidate.candidate_id,),
            proposal_sha256="0" * 64,
        )
        relabeled_proposal = replace(
            relabeled_proposal,
            proposal_sha256=relabeled_proposal.expected_digest(),
        )
        forged_profile_proposal = replace(
            handoff.proposal,
            intended_profile_id="profile-forged",
            proposal_sha256="0" * 64,
        )
        forged_profile_proposal = replace(
            forged_profile_proposal,
            proposal_sha256=forged_profile_proposal.expected_digest(),
        )
        forged_geometry_proposal = replace(
            handoff.proposal,
            abi_geometry="geometry-forged",
            proposal_sha256="0" * 64,
        )
        forged_geometry_proposal = replace(
            forged_geometry_proposal,
            proposal_sha256=forged_geometry_proposal.expected_digest(),
        )
        substitutions = (
            self._rehash_handoff(handoff, staged_candidate=forged_candidate),
            self._rehash_handoff(handoff, staged_candidate=forged_sense),
            self._rehash_handoff(handoff, staged_candidate=forged_anchor),
            self._rehash_handoff(
                handoff,
                staged_candidate=relabeled_candidate,
                proposal=relabeled_proposal,
            ),
            self._rehash_handoff(handoff, proposal=forged_profile_proposal),
            self._rehash_handoff(handoff, proposal=forged_geometry_proposal),
            self._rehash_handoff(handoff, family_ids=("family:forged",)),
            self._rehash_handoff(handoff, operator_scopes=(replace(
                handoff.operator_scopes[0],
                source_adapter_id="source.forged/v1"),)),
        )
        for forged in substitutions:
            with self.subTest(field=forged):
                with self.assertRaises(BilqisError):
                    forged.verify()

    def test_missing_source_operator_authority_fails_closed(self):
        with patch(
            "bilqis_mlx.factory.atlas_delta_scope.source_operator_disposition",
            return_value=None,
        ), patch(
            "bilqis_mlx.factory.candidate_realizations.project_realized_target",
            side_effect=self._authority,
        ), patch(
            "bilqis_mlx.factory.atlas_frontier_progress_validation.project_realized_target",
            side_effect=self._authority,
        ), patch(
            "bilqis_mlx.factory.candidate_realizations.realized_source_sense_id",
            return_value=self.staged.source_sense_id,
        ):
            with self.assertRaises(BilqisError) as caught:
                next_atlas_delta(self._epoch(), self.learner, self.plan)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_ATLAS_DELTA_OPERATOR_SCOPE_UNSUPPORTED",
        )

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
            handoff = next_atlas_delta(self._epoch(), self.learner, self.plan)
        self.assertIsInstance(handoff, AtlasDeltaScopeHandoff)
        proposal = handoff.proposal
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

if __name__ == "__main__":
    unittest.main()
