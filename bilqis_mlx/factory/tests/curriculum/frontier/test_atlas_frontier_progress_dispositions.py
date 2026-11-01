"""A09.4 typed terminal/blocked dispositions and authority-bound replay."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.atlas_frontier_closure import ClosureReason, ClosureStatus
from bilqis_mlx.factory.atlas_frontier_progress import (
    FrontierStatus, plan_frontier_progress,
)
from bilqis_mlx.factory.atlas_frontier_progress_contracts import StagedSelectionReceipt
from bilqis_mlx.factory.atlas_frontier_selection import select_frontier_delta
from bilqis_mlx.factory.skos_curriculum import IMPLEMENTATION_UNCOVERED
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import rehash
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_progress import (
    _stage, _staged_ready,
)
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_selection import (
    _candidate, _closure, _options, _release, _snapshot,
)
from bilqis_mlx.factory.tests.curriculum.frontier.test_candidate_staging import (
    CandidateStagingFixture,
)


def _admit(prior, snapshot, closure, receipt):
    admitted = rehash(
        snapshot,
        admitted_factory_release_sha256=receipt.staged_successor_sha256,
        admission_receipt_sha256="a" * 64,
        predecessor_sha256=snapshot.snapshot_sha256,
        event_generation=snapshot.event_generation + 1,
    )
    admitted_closure = _closure(admitted, tuple(
        _candidate(admitted, identity)
        for identity in admitted.source_eligible_concept_ids))
    return plan_frontier_progress(admitted, admitted_closure, prior=prior)


def _single_ready():
    fixture = CandidateStagingFixture()
    fixture.setUp()
    staged = fixture.stage()
    release = fixture.current
    snapshot = _snapshot(release)
    snapshot = rehash(
        snapshot,
        source_eligible_concept_ids=("z.op.0",),
        coverage_rows=tuple(row for row in snapshot.coverage_rows
                            if row.semantic_id == "z.op.0"),
        prerequisite_edges=(), source_held_rows=(), cursor=0,
        staged_factory_release_sha256s=(staged.successor.release_sha256,),
    )
    closure = _closure(snapshot, (_candidate(snapshot, "z.op.0"),))
    projections = _options(
        snapshot, release, closure,
        capabilities={"z.op.0": staged.successor.transition.added_capabilities},
        identities={"z.op.0": ()})
    selection = select_frontier_delta(snapshot, closure, release, projections)
    projection = next(
        item for item in projections
        if item.semantic_id == selection.selected_semantic_id)
    receipt = _stage(selection, projection, release, staged.successor)
    return snapshot, closure, selection, receipt


class AtlasFrontierProgressDispositionTests(unittest.TestCase):
    def test_staged_successor_must_match_exact_selection_delta(self):
        fixture = CandidateStagingFixture()
        fixture.setUp()
        staged = fixture.stage()
        snapshot = _snapshot(fixture.current)
        snapshot = rehash(
            snapshot, staged_factory_release_sha256s=(staged.successor.release_sha256,))
        closure = _closure(snapshot, tuple(
            _candidate(snapshot, identity) for identity in snapshot.source_eligible_concept_ids))
        projections = _options(snapshot, fixture.current, closure)
        mismatched = select_frontier_delta(
            snapshot, closure, fixture.current, projections)
        projection = next(
            item for item in projections
            if item.semantic_id == mismatched.selected_semantic_id)
        forged = _stage(
            mismatched, projection, fixture.current, staged.successor)
        with self.assertRaises(BilqisError):
            plan_frontier_progress(
                snapshot, closure, mismatched,
                current_release=fixture.current,
                selected_projection=projection,
                staged_receipt=forged)

    def test_direct_uncovered_count_excludes_propagated_dependents(self):
        release = _release()
        snapshot = _snapshot(release, prerequisite_edges=())
        # Construct the two dependency edges from the canonical edge type.
        from bilqis_mlx.factory.atlas_frontier_contracts import PrerequisiteEdge
        snapshot = rehash(
            snapshot,
            prerequisite_edges=(
                PrerequisiteEdge("z.op.1", "z.op.0", "a" * 64),
                PrerequisiteEdge("z.op.2", "z.op.0", "b" * 64),
            ),
            coverage_rows=tuple(
                replace(row, implementation_status=IMPLEMENTATION_UNCOVERED)
                if row.semantic_id == "z.op.0" else row
                for row in snapshot.coverage_rows),
        )
        direct = ClosureReason(
            "FAMILY_IMPLEMENTATION_UNCOVERED", "family:positive_identity")
        inherited = ClosureReason(
            "PREREQUISITE_IMPLEMENTATION_UNCOVERED", "factory:prerequisite", "z.op.0")
        closure = _closure(snapshot, (
            _candidate(snapshot, "z.op.0", status=ClosureStatus.IMPLEMENTATION_UNCOVERED,
                       reasons=(direct,)),
            _candidate(snapshot, "z.op.1", status=ClosureStatus.IMPLEMENTATION_UNCOVERED,
                       reasons=(inherited,)),
            _candidate(snapshot, "z.op.2", status=ClosureStatus.IMPLEMENTATION_UNCOVERED,
                       reasons=(inherited,)),
        ))
        result = plan_frontier_progress(snapshot, closure)
        self.assertEqual(result.status, FrontierStatus.IMPLEMENTATION_UNCOVERED)
        self.assertEqual(result.implementation_uncovered_count, 1)

    def test_requested_root_allows_evidence_wait_to_surface_without_busy_loop(self):
        release, snapshot, closure, selection, receipt = _staged_ready()
        prior = plan_frontier_progress(
            snapshot, closure, selection,
            current_release=release, selected_projection=receipt.projection,
            staged_receipt=receipt)
        advanced = _admit(prior, snapshot, closure, receipt)
        planning = advanced.planning_snapshot
        from bilqis_mlx.factory.atlas_frontier_contracts import PrerequisiteEdge
        planning = rehash(
            planning,
            prerequisite_edges=(
                PrerequisiteEdge("z.op.1", "z.op.0", "a" * 64),
                PrerequisiteEdge("z.op.2", "z.op.0", "b" * 64),
            ),
            predecessor_sha256=advanced.planning_snapshot.snapshot_sha256,
            event_generation=advanced.planning_snapshot.event_generation + 1,
        )
        wait = ClosureReason(
            "PREREQUISITE_WAITING_FOR_EVIDENCE", "factory:prerequisite", "z.op.0")
        waiting = _closure(planning, (
            _candidate(planning, "z.op.0"),
            _candidate(planning, "z.op.1", status=ClosureStatus.WAITING_FOR_EVIDENCE,
                       reasons=(wait,)),
            _candidate(planning, "z.op.2", status=ClosureStatus.WAITING_FOR_EVIDENCE,
                       reasons=(wait,)),
        ))
        result = plan_frontier_progress(planning, waiting, prior=advanced)
        self.assertEqual(result.status, FrontierStatus.WAITING_FOR_EVIDENCE)
        self.assertEqual(result.waiting_for_evidence_count, 2)

    def test_held_only_frontier_terminates_as_source_held(self):
        release = _release()
        snapshot = _snapshot(release)
        snapshot = rehash(
            snapshot, source_eligible_concept_ids=(), required_source_family_ids=(),
            coverage_rows=(), prerequisite_edges=(), cursor=0)
        closure = _closure(snapshot, ())
        result = plan_frontier_progress(snapshot, closure)
        self.assertEqual(result.status, FrontierStatus.SOURCE_HELD)
        self.assertEqual(result.source_held_count, 1)
        self.assertEqual(result, plan_frontier_progress(snapshot, closure))

    def test_complete_requires_requested_eligible_coverage_and_zero_debt(self):
        snapshot, closure, selection, receipt = _single_ready()
        prior = plan_frontier_progress(
            snapshot, closure, selection,
            current_release=receipt.predecessor_release,
            selected_projection=receipt.projection,
            staged_receipt=receipt)
        advanced = _admit(prior, snapshot, closure, receipt)
        planning = advanced.planning_snapshot
        final_closure = _closure(planning, (_candidate(planning, "z.op.0"),))
        complete = plan_frontier_progress(planning, final_closure, prior=advanced)
        self.assertEqual(complete.status, FrontierStatus.COMPLETE_ATLAS_COVERAGE)

        debt_snapshot = rehash(
            planning,
            coverage_rows=tuple(
                replace(row, implementation_status=IMPLEMENTATION_UNCOVERED)
                for row in planning.coverage_rows),
            predecessor_sha256=planning.snapshot_sha256,
            event_generation=planning.event_generation + 1,
        )
        direct = ClosureReason(
            "FAMILY_IMPLEMENTATION_UNCOVERED", "family:positive_identity")
        debt_closure = _closure(debt_snapshot, (_candidate(
            debt_snapshot, "z.op.0", status=ClosureStatus.IMPLEMENTATION_UNCOVERED,
            reasons=(direct,)),))
        debt = plan_frontier_progress(debt_snapshot, debt_closure, prior=advanced)
        self.assertEqual(debt.status, FrontierStatus.IMPLEMENTATION_UNCOVERED)

if __name__ == "__main__":
    unittest.main()
