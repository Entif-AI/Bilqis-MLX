from contextlib import ExitStack
import unittest
from unittest.mock import patch

from bilqis_mlx.factory.atlas_frontier import AtlasCoverageEpoch, AtlasLearnerEvidence
from bilqis_mlx.factory.atlas_frontier_progress import FrontierStatus
from bilqis_mlx.factory.autonomy import compile_autonomy_plan, initial_evidence_ledger
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_delta_adapter_fixtures import (
    AtlasDeltaAdapterFixture,
)
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import (
    rehash,
)
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_selection import (
    _candidate,
    _closure,
)
from bilqis_mlx.runtime.atlas_admission_policy import AdmissionResult, AdmissionStatus
from bilqis_mlx.runtime.autonomy_loop import (
    AdmissionFlywheelState,
    AdmissionFlywheelStatus,
    run_admission_flywheel,
)


class AdmissionFlywheelTests(AtlasDeltaAdapterFixture):
    def state(self, *, epoch=None, learner=None, plan=None):
        return AdmissionFlywheelState(
            epoch or self._epoch(), learner or self.learner, plan or self.plan)

    def planner_authority(self):
        stack = ExitStack()
        stack.enter_context(patch(
            "bilqis_mlx.factory.candidate_realizations.project_realized_target",
            side_effect=self._authority))
        stack.enter_context(patch(
            "bilqis_mlx.factory.atlas_frontier_progress_validation.project_realized_target",
            side_effect=self._authority))
        stack.enter_context(patch(
            "bilqis_mlx.factory.candidate_realizations.realized_source_sense_id",
            return_value=self.staged.source_sense_id))
        return stack

    def staged_result(self, handoff, reason="V2_ATLAS_LEASE_REQUIRED"):
        return AdmissionResult(
            AdmissionStatus.STAGED,
            handoff.proposal.proposal_sha256,
            None,
            self.current.release_sha256,
            handoff.staged_candidate.successor.release_sha256,
            reason,
            "Retain current accepted state; external authority must resolve the hold.",
        )

    def adopted_result(self, handoff):
        return AdmissionResult(
            AdmissionStatus.ADOPTED,
            handoff.proposal.proposal_sha256,
            "1" * 64,
            self.current.release_sha256,
            handoff.staged_candidate.successor.release_sha256,
            "ADOPTED",
            "Reload accepted custody before replanning.",
            state_adopted=True,
            requires_cold_resume=True,
            accepted_generation=1,
            accepted_manifest_sha256="2" * 64,
        )

    def successor_state(self, handoff):
        successor = handoff.staged_candidate.successor
        snapshot = rehash(
            self.snapshot,
            admitted_factory_release_sha256=successor.release_sha256,
            admission_receipt_sha256="8" * 64,
            staged_factory_release_sha256s=(),
            event_generation=self.snapshot.event_generation + 1,
            predecessor_sha256=self.snapshot.snapshot_sha256,
        )
        closure = _closure(snapshot, tuple(
            _candidate(snapshot, identity)
            for identity in snapshot.source_eligible_concept_ids))
        epoch = AtlasCoverageEpoch(
            snapshot, closure, self.frontier, successor, (), None, None)
        plan = compile_autonomy_plan(successor)
        learner = AtlasLearnerEvidence(
            initial_evidence_ledger(successor, plan=plan), "f" * 64, 1)
        return self.state(epoch=epoch, learner=learner, plan=plan)

    def test_real_planner_proposal_yields_lease_required_without_polling(self):
        state = self.state()
        for reason in ("V2_ATLAS_LEASE_REQUIRED", "OUT_OF_LEASE_SCOPE"):
            with self.subTest(reason=reason), self.planner_authority():
                result = run_admission_flywheel(
                    lambda: state,
                    lambda handoff: self.staged_result(handoff, reason),
                )
            self.assertEqual(result.status, AdmissionFlywheelStatus.LEASE_REQUIRED)
            self.assertEqual(result.reason, reason)
            self.assertEqual(result.advances, 0)
            self.assertIs(result.final_state, state)

    def test_planner_terminal_statuses_map_without_admission_authority(self):
        state = self.state()
        cases = (
            (FrontierStatus.FIXED_POINT, AdmissionFlywheelStatus.FIXED_POINT),
            (FrontierStatus.COMPLETE_ATLAS_COVERAGE,
             AdmissionFlywheelStatus.FIXED_POINT),
            (FrontierStatus.WAITING_FOR_EVIDENCE,
             AdmissionFlywheelStatus.WAITING_FOR_EVIDENCE),
            (FrontierStatus.SOURCE_HELD, AdmissionFlywheelStatus.HELD),
            (FrontierStatus.IMPLEMENTATION_UNCOVERED,
             AdmissionFlywheelStatus.IMPLEMENTATION_UNCOVERED),
            (FrontierStatus.LEASE_REQUIRED,
             AdmissionFlywheelStatus.LEASE_REQUIRED),
        )
        for planner_status, expected in cases:
            with self.subTest(planner_status=planner_status), patch(
                    "bilqis_mlx.runtime.autonomy_loop.next_atlas_delta",
                    return_value=planner_status):
                result = run_admission_flywheel(
                    lambda: state,
                    lambda _handoff: self.fail("terminal planner status dispatched"))
            self.assertEqual(result.status, expected)
            self.assertEqual(result.reason, planner_status.value)
            self.assertEqual(result.advances, 0)

    def test_adopted_result_without_matching_accepted_release_holds(self):
        state = self.state()
        handoff = self._handoff()
        with patch(
                "bilqis_mlx.runtime.autonomy_loop.next_atlas_delta",
                return_value=handoff):
            result = run_admission_flywheel(
                lambda: state,
                lambda item: self.adopted_result(item),
            )
        self.assertEqual(result.status, AdmissionFlywheelStatus.HELD)
        self.assertEqual(result.reason, "ADOPTED_STATE_BINDING_DRIFT")
        self.assertEqual(result.advances, 0)

    def test_replan_without_state_advance_holds_instead_of_polling(self):
        state = self.state()
        with patch(
                "bilqis_mlx.runtime.autonomy_loop.next_atlas_delta",
                return_value=FrontierStatus.REPLAN_REQUIRED):
            result = run_admission_flywheel(
                lambda: state,
                lambda _handoff: self.fail("replan status dispatched"),
            )
        self.assertEqual(result.status, AdmissionFlywheelStatus.HELD)
        self.assertEqual(result.reason, "REPLAN_WITHOUT_STATE_ADVANCE")
        self.assertEqual(result.advances, 0)

    def test_admission_result_must_bind_exact_planner_handoff(self):
        state = self.state()
        handoff = self._handoff()
        forged = AdmissionResult(
            AdmissionStatus.STAGED,
            "f" * 64,
            None,
            self.current.release_sha256,
            handoff.staged_candidate.successor.release_sha256,
            "V2_ATLAS_LEASE_REQUIRED",
            "forged proposal identity",
        )
        with patch(
                "bilqis_mlx.runtime.autonomy_loop.next_atlas_delta",
                return_value=handoff):
            result = run_admission_flywheel(lambda: state, lambda _item: forged)
        self.assertEqual(result.status, AdmissionFlywheelStatus.HELD)
        self.assertEqual(result.reason, "ADMISSION_RESULT_BINDING_DRIFT")
        self.assertEqual(result.advances, 0)

    def test_adopted_successor_replans_once_only_after_bound_state_advance(self):
        first = self.state()
        handoff = self._handoff()
        second = self.successor_state(handoff)
        states = iter((first, second))
        with patch(
                "bilqis_mlx.runtime.autonomy_loop.next_atlas_delta",
                side_effect=(handoff, FrontierStatus.FIXED_POINT)):
            result = run_admission_flywheel(
                lambda: next(states),
                lambda item: self.adopted_result(item),
                max_advances=1,
            )
        self.assertEqual(result.status, AdmissionFlywheelStatus.FIXED_POINT)
        self.assertEqual(result.reason, "FIXED_POINT")
        self.assertEqual(result.advances, 1)
        self.assertIs(result.final_state, second)


if __name__ == "__main__":
    unittest.main()
