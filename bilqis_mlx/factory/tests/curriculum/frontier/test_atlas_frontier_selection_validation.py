"""A09.3 fail-closed closure and exact future-shape projection regressions."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.atlas_frontier_closure import ClosureReason, ClosureStatus
from bilqis_mlx.factory.atlas_frontier_contracts import PlannerBudget
from bilqis_mlx.factory.atlas_frontier_selection import select_frontier_delta
from bilqis_mlx.factory.skos_curriculum import IMPLEMENTATION_UNCOVERED, PROGRAM_BOUND
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import rehash
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_selection import (
    _candidate, _closure, _options, _release, _snapshot,
)


class AtlasFrontierSelectionValidationTests(unittest.TestCase):
    def test_remainder_preserves_typed_reason_owner_and_dependency(self):
        release = _release()
        snapshot = _snapshot(release)
        reason = ClosureReason(
            "PREREQUISITE_WAITING_FOR_EVIDENCE", "factory:prerequisite", "z.op.0")
        closure = _closure(snapshot, (
            _candidate(snapshot, "z.op.0"),
            _candidate(snapshot, "z.op.1", status=ClosureStatus.WAITING_FOR_EVIDENCE,
                       reasons=(reason,)),
            _candidate(snapshot, "z.op.2"),
        ))
        selection = select_frontier_delta(
            snapshot, closure, release, _options(snapshot, release, closure))
        deferred = next(item for item in selection.deferred if item.semantic_id == "z.op.1")
        self.assertEqual(deferred.reasons, (reason,))

    def test_no_capability_budget_fails_closed(self):
        release = _release()
        snapshot = _snapshot(release, budget=PlannerBudget(0, 16, 1000))
        closure = _closure(snapshot, tuple(
            _candidate(snapshot, identity) for identity in snapshot.source_eligible_concept_ids))
        with self.assertRaises(BilqisError):
            select_frontier_delta(
                snapshot, closure, release, _options(snapshot, release, closure))

    def test_forged_ready_status_and_omitted_family_fail_closed(self):
        release = _release()
        snapshot = _snapshot(release)
        uncovered = replace(
            snapshot.coverage_rows[0], implementation_status=IMPLEMENTATION_UNCOVERED)
        snapshot = rehash(snapshot, coverage_rows=tuple(sorted(
            (uncovered,) + snapshot.coverage_rows[1:],
            key=lambda item: (item.semantic_id, item.family_id))))
        forged = _closure(snapshot, tuple(
            _candidate(snapshot, identity) for identity in snapshot.source_eligible_concept_ids))
        with self.assertRaises(BilqisError):
            select_frontier_delta(
                snapshot, forged, release, _options(snapshot, release, forged))

        two_family = rehash(snapshot, coverage_rows=tuple(sorted(
            snapshot.coverage_rows + (replace(
                snapshot.coverage_rows[0], family_id="numeric_composition",
                source_evidence_sha256="b" * 64, implementation_status=PROGRAM_BOUND),),
            key=lambda item: (item.semantic_id, item.family_id))),
            required_source_family_ids=("numeric_composition", "positive_identity"))
        omitted = _closure(two_family, tuple(
            _candidate(two_family, identity) for identity in two_family.source_eligible_concept_ids))
        with self.assertRaises(BilqisError):
            select_frontier_delta(
                two_family, omitted, release, _options(two_family, release, omitted))

    def test_impossible_prerequisite_reason_dependency_fails_closed(self):
        release = _release()
        snapshot = _snapshot(release)
        impossible = ClosureReason(
            "PREREQUISITE_WAITING_FOR_EVIDENCE", "factory:prerequisite", "z.op.2")
        closure = _closure(snapshot, (
            _candidate(snapshot, "z.op.0"),
            _candidate(snapshot, "z.op.1", status=ClosureStatus.WAITING_FOR_EVIDENCE,
                       reasons=(impossible,)),
            _candidate(snapshot, "z.op.2"),
        ))
        with self.assertRaises(BilqisError):
            select_frontier_delta(
                snapshot, closure, release, _options(snapshot, release, closure))

    def test_exact_projection_controls_capability_and_zero_identity_budget(self):
        release = _release()
        snapshot = _snapshot(release, budget=PlannerBudget(1, 0, 1000))
        closure = _closure(snapshot, tuple(
            _candidate(snapshot, identity) for identity in snapshot.source_eligible_concept_ids))
        options = _options(snapshot, release, closure, identities={
            "z.op.0": (), "z.op.1": (), "z.op.2": (),
        })
        selection = select_frontier_delta(snapshot, closure, release, options)
        self.assertEqual(selection.introduced_semantic_ids, ())
        self.assertEqual(len(selection.introduced_capability_ids), 1)

        oversized = _options(snapshot, release, closure, capabilities={
            "z.op.0": ("Z.N0", "Z.N0.EXTRA"),
            "z.op.1": ("Z.N1",), "z.op.2": ("Z.N2",),
        }, identities={"z.op.0": (), "z.op.1": (), "z.op.2": ()})
        with self.assertRaises(BilqisError):
            select_frontier_delta(snapshot, closure, release, oversized)

    def test_exact_identity_projection_is_not_a_semantic_root_proxy(self):
        release = _release()
        snapshot = _snapshot(release, budget=PlannerBudget(9, 1, 1000))
        closure = _closure(snapshot, tuple(
            _candidate(snapshot, identity) for identity in snapshot.source_eligible_concept_ids))
        options = _options(snapshot, release, closure, identities={
            "z.op.0": ("fixture.appended.identity", "fixture.second.identity"),
            "z.op.1": ("z.op.1",), "z.op.2": ("z.op.2",),
        })
        with self.assertRaises(BilqisError):
            select_frontier_delta(snapshot, closure, release, options)


if __name__ == "__main__":
    unittest.main()
