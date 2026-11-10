from dataclasses import replace
import unittest
from unittest.mock import patch

from bilqis_mlx.factory.atlas_frontier import (
    AtlasCoverageEpoch, AtlasLearnerEvidence, next_atlas_delta,
)
from bilqis_mlx.factory.atlas_delta_scope import AtlasDeltaScopeHandoff
from bilqis_mlx.factory.autonomy import compile_autonomy_plan, initial_evidence_ledger
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import rehash
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_selection import (
    _candidate, _closure, _snapshot,
)
from bilqis_mlx.factory.tests.curriculum.frontier.test_candidate_staging import CandidateStagingFixture
from bilqis_mlx.source_adapters.formal_identity import (
    OperatorDispositionKind, SourceOperatorDisposition,
)


class AtlasDeltaAdapterFixture(unittest.TestCase):
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
        execution = self.staged.successor.execution_plan.capability_map["Z.C6"]
        descriptor = next(
            item for item in self.staged.successor.source_adapters
            if item.adapter_id == execution.provider_id)
        fixture_disposition = SourceOperatorDisposition(
            capability_id="Z.C6", source_adapter_id=descriptor.adapter_id,
            kind=OperatorDispositionKind.NON_OPERATOR,
            operator_id=None, semantic_root=None,
            generator_id=descriptor.generator_id,
            accepted_oracle_ids=descriptor.accepted_oracle_ids,
            implementation_sha256=descriptor.implementation_sha256,
        )
        operator_patch = patch(
            "bilqis_mlx.factory.atlas_delta_scope.source_operator_disposition",
            return_value=fixture_disposition)
        operator_patch.start()
        self.addCleanup(operator_patch.stop)

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

    def _handoff(self):
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
        return handoff

    @staticmethod
    def _rehash_handoff(handoff, **changes):
        changed = replace(handoff, handoff_sha256="0" * 64, **changes)
        return replace(changed, handoff_sha256=changed.expected_digest())

    @staticmethod
    def _rehash_staged(staged, **changes):
        changed = replace(staged, staged_sha256="0" * 64, **changes)
        return replace(changed, staged_sha256=changed.expected_digest())

    @staticmethod
    def _rehash_proposal(proposal, **changes):
        changed = replace(proposal, proposal_sha256="0" * 64, **changes)
        return replace(changed, proposal_sha256=changed.expected_digest())

    @staticmethod
    def _forged_receipt(handoff):
        forged_snapshot = rehash(
            handoff.receipt.selection_snapshot,
            candidate_frontier_sha256="f" * 64,
        )
        forged_selection = replace(
            handoff.receipt.selection,
            snapshot_sha256=forged_snapshot.snapshot_sha256,
            selection_sha256="0" * 64,
        )
        forged_selection = replace(
            forged_selection,
            selection_sha256=forged_selection.expected_digest(),
        )
        forged_receipt = replace(
            handoff.receipt,
            selection=forged_selection,
            selection_snapshot=forged_snapshot,
            receipt_sha256="0" * 64,
        )
        return replace(
            forged_receipt, receipt_sha256=forged_receipt.expected_digest())

    def _adversarial_handoff_substitutions(self, handoff):
        forged_candidate = self._rehash_staged(
            handoff.staged_candidate, candidate_id="candidate-forged")
        forged_sense = self._rehash_staged(
            handoff.staged_candidate, source_sense_id="sense:forged")
        forged_anchor = self._rehash_staged(
            handoff.staged_candidate, source_anchor="source:forged")
        relabeled_candidate = self._rehash_staged(
            handoff.staged_candidate, candidate_id="candidate-forged")
        relabeled_proposal = self._rehash_proposal(
            handoff.proposal,
            selected_candidate_ids=(relabeled_candidate.candidate_id,),
        )
        forged_profile = self._rehash_proposal(
            handoff.proposal, intended_profile_id="profile-forged")
        forged_geometry = self._rehash_proposal(
            handoff.proposal, abi_geometry="geometry-forged")
        return (
            self._rehash_handoff(handoff, staged_candidate=forged_candidate),
            self._rehash_handoff(handoff, staged_candidate=forged_sense),
            self._rehash_handoff(handoff, staged_candidate=forged_anchor),
            self._rehash_handoff(
                handoff, staged_candidate=relabeled_candidate,
                proposal=relabeled_proposal),
            self._rehash_handoff(handoff, proposal=forged_profile),
            self._rehash_handoff(handoff, proposal=forged_geometry),
            self._rehash_handoff(handoff, receipt=self._forged_receipt(handoff)),
            self._rehash_handoff(handoff, family_ids=("family:forged",)),
            self._rehash_handoff(handoff, operator_scopes=(replace(
                handoff.operator_scopes[0],
                source_adapter_id="source.forged/v1"),)),
        )
