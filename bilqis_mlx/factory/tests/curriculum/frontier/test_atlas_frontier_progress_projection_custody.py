"""A09.4 regressions for exact A09.3 projection custody (ADR-122)."""
from dataclasses import replace
import hashlib
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.atlas_frontier_contracts import _bytes
from bilqis_mlx.factory.atlas_frontier_progress import plan_frontier_progress
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_progress import (
    _ready,
    _staged_ready,
)
from bilqis_mlx.factory.tests.curriculum.frontier.test_atlas_frontier_selection import (
    _options,
)


def _forge_selection(selection, *, capabilities=None, identities=None):
    capabilities = capabilities or selection.introduced_capability_ids
    identities = identities if identities is not None else selection.introduced_semantic_ids
    obligations = tuple(
        (row.family_id, row.source_evidence_sha256, row.prerequisites)
        for row in selection.selected_obligations)
    signature = hashlib.sha256(_bytes({
        "semantic_id": selection.selected_semantic_id,
        "obligations": obligations,
        "introduced_capability_ids": capabilities,
        "introduced_semantic_ids": identities,
    })).hexdigest()
    forged = replace(
        selection,
        introduced_capability_ids=capabilities,
        introduced_semantic_ids=identities,
        candidate_signature=signature,
        selection_sha256="0" * 64,
    )
    return replace(forged, selection_sha256=forged.expected_digest())


class AtlasFrontierProjectionCustodyTests(unittest.TestCase):
    def test_direct_proposal_requires_release_and_projection_evidence(self):
        _, snapshot, closure, selection = _ready()

        with self.assertRaises(BilqisError):
            plan_frontier_progress(snapshot, closure, selection)

    def test_same_semantic_capability_forgery_fails_closed(self):
        release, snapshot, closure, selection = _ready()
        projection = next(
            item for item in _options(snapshot, release, closure)
            if item.semantic_id == selection.selected_semantic_id)
        forged = _forge_selection(selection, capabilities=("Z.FORGED",))

        with self.assertRaises(BilqisError):
            plan_frontier_progress(
                snapshot, closure, forged,
                current_release=release,
                selected_projection=projection,
            )

    def test_same_semantic_identity_forgery_fails_closed(self):
        release, snapshot, closure, selection = _ready()
        projection = next(
            item for item in _options(snapshot, release, closure)
            if item.semantic_id == selection.selected_semantic_id)
        forged = _forge_selection(
            selection, identities=("fixture.forged.semantic",))

        with self.assertRaises(BilqisError):
            plan_frontier_progress(
                snapshot, closure, forged,
                current_release=release,
                selected_projection=projection,
            )

    def test_cold_resume_rejects_self_rehashed_forged_projection_custody(self):
        release, snapshot, closure, selection, receipt = _staged_ready()
        prior = plan_frontier_progress(
            snapshot, closure, selection,
            current_release=release,
            selected_projection=receipt.projection,
            staged_receipt=receipt,
        )
        forged_projection = replace(
            receipt.projection,
            added_capability_ids=("Z.FORGED",),
            projection_sha256="0" * 64,
        )
        forged_projection = replace(
            forged_projection,
            projection_sha256=forged_projection.expected_digest(),
        )
        forged_receipt = replace(
            receipt,
            projection=forged_projection,
            receipt_sha256="0" * 64,
        )
        forged_receipt = replace(
            forged_receipt,
            receipt_sha256=forged_receipt.expected_digest(),
        )
        forged_prior = replace(
            prior,
            staged_receipts=(forged_receipt,),
            pending_staged_receipt_sha256=forged_receipt.receipt_sha256,
            progress_sha256="0" * 64,
        )
        forged_prior = replace(
            forged_prior,
            progress_sha256=forged_prior.expected_digest(),
        )

        with self.assertRaises(BilqisError):
            plan_frontier_progress(snapshot, closure, prior=forged_prior)


if __name__ == "__main__":
    unittest.main()
