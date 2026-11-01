"""A09.4 resumable coverage progress and fixed-point behavior."""
from dataclasses import replace
import unittest

from bilqis_mlx.factory.atlas_frontier_progress import (
    FrontierStatus,
    plan_frontier_progress,
)
from bilqis_mlx.factory.atlas_frontier_progress_contracts import StagedSelectionReceipt
from bilqis_mlx.factory.atlas_frontier_closure import ClosureReason, ClosureStatus
from bilqis_mlx.factory.skos_curriculum import IMPLEMENTATION_UNCOVERED
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import rehash
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_selection import (
    _candidate, _closure, _options, _release, _snapshot,
)
from bilqis_mlx.factory.tests.curriculum.frontier.test_candidate_staging import (
    CandidateStagingFixture,
)
from bilqis_mlx.factory.atlas_frontier_selection import select_frontier_delta


def _ready(*, staged_sha=None):
    release = _release()
    snapshot = _snapshot(release)
    if staged_sha is not None:
        snapshot = rehash(
            snapshot, staged_factory_release_sha256s=(staged_sha,))
    closure = _closure(snapshot, tuple(
        _candidate(snapshot, identity) for identity in snapshot.source_eligible_concept_ids))
    selection = select_frontier_delta(
        snapshot, closure, release, _options(snapshot, release, closure))
    return release, snapshot, closure, selection


def _stage(selection, predecessor, successor):
    provisional = StagedSelectionReceipt(
        selection, predecessor, successor, "0" * 64)
    return replace(provisional, receipt_sha256=provisional.expected_digest())


def _staged_ready():
    fixture = CandidateStagingFixture()
    fixture.setUp()
    staged = fixture.stage()
    release = fixture.current
    snapshot = _snapshot(release)
    snapshot = rehash(
        snapshot, staged_factory_release_sha256s=(staged.successor.release_sha256,))
    closure = _closure(snapshot, tuple(
        _candidate(snapshot, identity) for identity in snapshot.source_eligible_concept_ids))
    capabilities = {
        "z.op.0": staged.successor.transition.added_capabilities,
        "z.op.1": ("Z.N1",), "z.op.2": ("Z.N2",),
    }
    identities = {"z.op.0": (), "z.op.1": (), "z.op.2": ()}
    selection = select_frontier_delta(
        snapshot, closure, release,
        _options(snapshot, release, closure,
                 capabilities=capabilities, identities=identities))
    receipt = _stage(selection, release, staged.successor)
    return release, snapshot, closure, selection, receipt


class AtlasFrontierProgressTests(unittest.TestCase):
    def test_identical_ready_inputs_emit_byte_identical_proposal(self):
        _, snapshot, closure, selection = _ready()
        first = plan_frontier_progress(snapshot, closure, selection)
        second = plan_frontier_progress(snapshot, closure, selection)
        self.assertEqual(first, second)
        self.assertEqual(first.status, FrontierStatus.PROPOSAL)
        self.assertEqual(first.cursor, snapshot.cursor)
        self.assertEqual(first.proposal_selection_sha256, selection.selection_sha256)
        self.assertEqual(first.requested_semantic_ids, ())

    def test_staged_selection_preserves_cursor_and_requires_lease(self):
        release, staged_snapshot, closure, selection, receipt = _staged_ready()
        first = plan_frontier_progress(
            staged_snapshot, closure, selection, staged_receipt=receipt)
        replay = plan_frontier_progress(
            staged_snapshot, closure, selection, staged_receipt=receipt)
        self.assertEqual(first, replay)
        self.assertEqual(first.status, FrontierStatus.LEASE_REQUIRED)
        self.assertEqual(first.cursor, staged_snapshot.cursor)
        self.assertEqual(first.requested_semantic_ids, (selection.selected_semantic_id,))
        self.assertEqual(first.pending_staged_successor_sha256, receipt.staged_successor_sha256)
        self.assertEqual(first.pending_semantic_id, selection.selected_semantic_id)

    def test_cold_resume_of_pending_stage_does_not_duplicate_identity(self):
        release, staged_snapshot, closure, selection, receipt = _staged_ready()
        prior = plan_frontier_progress(
            staged_snapshot, closure, selection, staged_receipt=receipt)
        resumed = plan_frontier_progress(staged_snapshot, closure, selection, prior=prior)
        self.assertEqual(resumed.status, FrontierStatus.LEASE_REQUIRED)
        self.assertEqual(resumed.requested_semantic_ids, prior.requested_semantic_ids)
        self.assertEqual(resumed.cursor, prior.cursor)

    def test_reconciled_admission_advances_authoritative_snapshot_cursor_once(self):
        release, staged_snapshot, closure, selection, receipt = _staged_ready()
        prior = plan_frontier_progress(
            staged_snapshot, closure, selection, staged_receipt=receipt)
        admitted = rehash(
            staged_snapshot,
            admitted_factory_release_sha256=receipt.staged_successor_sha256,
            admission_receipt_sha256="a" * 64,
            predecessor_sha256=staged_snapshot.snapshot_sha256,
            event_generation=staged_snapshot.event_generation + 1,
        )
        admitted_closure = _closure(admitted, tuple(
            _candidate(admitted, identity)
            for identity in admitted.source_eligible_concept_ids))
        advanced = plan_frontier_progress(admitted, admitted_closure, prior=prior)
        expected_cursor = (
            admitted_closure.constituent_order.index(selection.selected_semantic_id) + 1
        ) % len(admitted_closure.constituent_order)
        self.assertEqual(advanced.status, FrontierStatus.FIXED_POINT)
        self.assertEqual(advanced.cursor, expected_cursor)
        self.assertEqual(advanced.planning_snapshot.predecessor_sha256,
                         admitted.snapshot_sha256)
        self.assertEqual(advanced.planning_snapshot.event_generation,
                         admitted.event_generation)
        replay = plan_frontier_progress(admitted, admitted_closure, prior=prior)
        self.assertEqual(advanced, replay)

    def test_uncovered_and_waiting_frontiers_terminate_with_exact_counts(self):
        _, snapshot, _, _ = _ready()
        snapshot = rehash(snapshot, coverage_rows=tuple(
            replace(row, implementation_status=IMPLEMENTATION_UNCOVERED)
            for row in snapshot.coverage_rows))
        uncovered = ClosureReason(
            "FAMILY_IMPLEMENTATION_UNCOVERED", "family:positive_identity")
        inherited = ClosureReason(
            "PREREQUISITE_IMPLEMENTATION_UNCOVERED",
            "factory:prerequisite", "z.op.0")
        closure = _closure(snapshot, (
            _candidate(snapshot, "z.op.0", status=ClosureStatus.IMPLEMENTATION_UNCOVERED,
                       reasons=(uncovered,)),
            _candidate(snapshot, "z.op.1", status=ClosureStatus.IMPLEMENTATION_UNCOVERED,
                       reasons=(uncovered, inherited)),
            _candidate(snapshot, "z.op.2", status=ClosureStatus.IMPLEMENTATION_UNCOVERED,
                       reasons=(uncovered,)),
        ))
        blocked = plan_frontier_progress(snapshot, closure)
        self.assertEqual(blocked.status, FrontierStatus.IMPLEMENTATION_UNCOVERED)
        self.assertEqual(blocked.implementation_uncovered_count, 3)
        self.assertEqual(blocked.source_held_count, 1)

        wait_reason = ClosureReason(
            "PREREQUISITE_WAITING_FOR_EVIDENCE", "factory:prerequisite", "z.op.0")
        waiting = _closure(snapshot, (
            _candidate(snapshot, "z.op.0"),
            _candidate(snapshot, "z.op.1", status=ClosureStatus.WAITING_FOR_EVIDENCE,
                       reasons=(wait_reason,)),
            _candidate(snapshot, "z.op.2"),
        ))
        # READY work still requires the concrete A09.3 proposal instead of hiding it.
        with self.assertRaises(Exception):
            plan_frontier_progress(snapshot, waiting)

    def test_epoch_changes_on_correction_but_preserves_prior_cursor_and_requests(self):
        release, staged_snapshot, closure, selection, receipt = _staged_ready()
        prior = plan_frontier_progress(
            staged_snapshot, closure, selection, staged_receipt=receipt)
        corrected = rehash(
            staged_snapshot,
            correction_generation=staged_snapshot.correction_generation + 1,
            event_generation=staged_snapshot.event_generation + 1,
            predecessor_sha256=staged_snapshot.snapshot_sha256,
        )
        corrected_closure = _closure(corrected, tuple(
            _candidate(corrected, identity)
            for identity in corrected.source_eligible_concept_ids))
        corrected_selection = select_frontier_delta(
            corrected, corrected_closure, _release(),
            _options(corrected, _release(), corrected_closure))
        result = plan_frontier_progress(
            corrected, corrected_closure, corrected_selection, prior=prior)
        self.assertNotEqual(result.coverage_epoch_sha256, prior.coverage_epoch_sha256)
        self.assertEqual(result.cursor, prior.cursor)
        self.assertEqual(result.requested_semantic_ids, prior.requested_semantic_ids)


if __name__ == "__main__":
    unittest.main()
