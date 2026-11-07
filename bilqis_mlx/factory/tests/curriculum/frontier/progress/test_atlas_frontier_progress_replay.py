"""A09.4 replay lineage and correction-specific reopening."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.atlas_frontier_progress import FrontierStatus, plan_frontier_progress
from bilqis_mlx.factory.atlas_frontier_selection import select_frontier_delta
from bilqis_mlx.factory.tests.curriculum.frontier.atlas_frontier_closure_fixtures import rehash
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_progress import (
    ProjectionAuthorityFixture, _staged_ready,
)
from bilqis_mlx.factory.tests.curriculum.frontier.progress.test_atlas_frontier_progress_dispositions import (
    _admit, _single_ready,
)
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_selection import (
    _candidate, _closure, _options,
)


class AtlasFrontierProgressReplayTests(ProjectionAuthorityFixture, unittest.TestCase):
    def test_changed_obligation_reopens_target_but_metadata_only_correction_does_not(self):
        snapshot, closure, selection, receipt = _single_ready()
        staged = plan_frontier_progress(
            snapshot, closure, selection,
            current_release=receipt.predecessor_release,
            selected_projection=receipt.projection,
            staged_receipt=receipt)
        advanced = _admit(staged, snapshot, closure, receipt)
        base = advanced.planning_snapshot
        current_release = receipt.staged_successor

        unchanged = rehash(
            base, correction_generation=base.correction_generation + 1,
            event_generation=base.event_generation + 1,
            predecessor_sha256=base.snapshot_sha256)
        unchanged_closure = _closure(unchanged, (_candidate(unchanged, "z.op.0"),))
        unchanged_projections = _options(
            unchanged, current_release, unchanged_closure,
            capabilities={"z.op.0": ("Z.NEXT",)}, identities={"z.op.0": ()})
        unchanged_selection = select_frontier_delta(
            unchanged, unchanged_closure, current_release, unchanged_projections)
        unchanged_projection = next(
            item for item in unchanged_projections
            if item.semantic_id == unchanged_selection.selected_semantic_id)
        fixed = plan_frontier_progress(
            unchanged, unchanged_closure, unchanged_selection,
            current_release=current_release,
            selected_projection=unchanged_projection,
            prior=advanced)
        self.assertEqual(fixed.status, FrontierStatus.FIXED_POINT)

        changed = rehash(
            unchanged,
            coverage_rows=(replace(
                unchanged.coverage_rows[0], source_evidence_sha256="c" * 64),),
            correction_generation=unchanged.correction_generation + 1,
            event_generation=unchanged.event_generation + 1,
            predecessor_sha256=unchanged.snapshot_sha256)
        changed_closure = _closure(changed, (_candidate(changed, "z.op.0"),))
        changed_projections = _options(
            changed, current_release, changed_closure,
            capabilities={"z.op.0": ("Z.NEXT",)}, identities={"z.op.0": ()})
        changed_selection = select_frontier_delta(
            changed, changed_closure, current_release, changed_projections)
        changed_projection = next(
            item for item in changed_projections
            if item.semantic_id == changed_selection.selected_semantic_id)
        reopened = plan_frontier_progress(
            changed, changed_closure, changed_selection,
            current_release=current_release,
            selected_projection=changed_projection,
            prior=fixed)
        self.assertEqual(reopened.status, FrontierStatus.PROPOSAL)

    def test_prior_progress_must_be_direct_lineage_not_unrelated_self_hash(self):
        _, snapshot, closure, selection, receipt = _staged_ready()
        prior = plan_frontier_progress(
            snapshot, closure, selection,
            current_release=receipt.predecessor_release,
            selected_projection=receipt.projection,
            staged_receipt=receipt)
        unrelated = rehash(
            snapshot, event_generation=snapshot.event_generation + 2,
            predecessor_sha256="d" * 64)
        unrelated_closure = _closure(unrelated, tuple(
            _candidate(unrelated, identity)
            for identity in unrelated.source_eligible_concept_ids))
        with self.assertRaises(BilqisError):
            plan_frontier_progress(unrelated, unrelated_closure, prior=prior)

    def test_receipt_schema_cannot_fork_same_staged_successor(self):
        _, snapshot, closure, selection, receipt = _staged_ready()
        forged = replace(receipt, schema="fixture/fork", receipt_sha256="0" * 64)
        forged = replace(forged, receipt_sha256=forged.expected_digest())
        with self.assertRaises(BilqisError):
            plan_frontier_progress(
                snapshot, closure, selection,
                current_release=receipt.predecessor_release,
                selected_projection=receipt.projection,
                staged_receipt=forged)


if __name__ == "__main__":
    unittest.main()
