"""Real-A01 page growth crosses B12/C05/B13 and survives cold continuation."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from bilqis_mlx.learning._engram.tests.motif_fixtures import full_first_page, source
from bilqis_mlx.learning._engram.tests.test_atlas_engram_source import (
    REAL_RELEASE, SourceQualifiedMotifTests,
)
from bilqis_mlx.learning._retention.tests.motif_allocation_support import (
    CandidateMotifAllocationFixture, MOTIF,
)
from bilqis_mlx.learning.atlas_candidate import resolve_candidate
from bilqis_mlx.learning.atlas_engram import (
    MOTIF_PAGE_STATE_BYTES, MotifBudget, MotifManifest, MotifSlot,
)
from bilqis_mlx.learning.atlas_engram_transaction import (
    CandidateMotifSnapshot, MotifAllocationSnapshot,
    _prepare_candidate_motif_snapshot,
)
from bilqis_mlx.runtime.bamf_bundle.admission import (
    accept_and_publish, derive_motif_successor_bundle, load_accepted_generation,
)
from bilqis_mlx.runtime.bamf_bundle.source_continuation import (
    continue_source_qualified_motifs_from_bundle,
    seal_source_qualified_motifs_from_bundle,
    stage_source_qualified_motif_allocation,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle import helpers
from bilqis_mlx.runtime.tests.custody.bamf_bundle.genesis_authority_fixtures import (
    genesis_feature_source_patch, issue_feature_authority, source_features,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import publish_genesis
from bilqis_mlx.runtime.tests.custody.bamf_bundle.publication.publication_helpers import (
    host_source_authority_patch,
)
from bilqis_mlx.semantics.context_eligibility import SourceFrontier

from .motif_publication_support import accepted_c05_decision


def _matching_source():
    item = source()
    frame = replace(item.frame, bindings=tuple(
        replace(binding, concept=replace(
            binding.concept, semantic_release=REAL_RELEASE))
        for binding in item.frame.bindings))
    return replace(item, frame=frame)


def _full_real_release_manifest():
    original = full_first_page()
    return MotifManifest(REAL_RELEASE, tuple(
        MotifSlot(slot.slot_id, replace(slot.key, semantic_release=REAL_RELEASE))
        for slot in original.slots))


def _seed_full_page_continuation(parent):
    base = _prepare_candidate_motif_snapshot(
        (_matching_source(),), parent.retained_state.allocations, MotifBudget(2))
    proposed = MotifAllocationSnapshot(_full_real_release_manifest())
    candidate = CandidateMotifSnapshot(
        parent.retained_state.allocations.digest, base.view, proposed)
    return SimpleNamespace(
        approved=SimpleNamespace(
            candidate=candidate, approved_context_digest="e" * 64),
        parent_manifest_sha256=parent.retained_state.custody.manifest_sha256,
        parent_extents_sha256=parent.extents.digest,
        parent_allocation_sha256=parent.retained_state.allocations.digest)


def _publish_staged(run_dir, parent, staged):
    retained = resolve_candidate(staged, accepted=True)
    successor = derive_motif_successor_bundle(
        parent, staged,
        parent_manifest_sha256=parent.retained_state.custody.manifest_sha256,
        delivery_events=({"event": "BAMF_GENERATION_ACCEPTED",
                          "optimizer_step": retained.optimizer_step},))
    decision = accepted_c05_decision(
        run_dir, staged, parent, successor, retained)
    pointer = accept_and_publish(
        run_dir, successor, retained, decision=decision,
        feature_sha256=successor.extents.factor_map_digest,
        reserve_gib=0., training_authorities=None)
    return retained, successor, pointer


@unittest.skipUnless(os.environ.get("BILQIS_ATLAS_REAL_ARTIFACT"),
                     "real repo-pinned A01 artifact required")
class MotifAllocationPageGrowthPublicationTests(unittest.TestCase):
    def test_real_a01_page_growth_publishes_and_cold_continues(self):
        fixture = CandidateMotifAllocationFixture()
        fixture.setUp()
        source_case = SourceQualifiedMotifTests(
            "test_real_source_replay_qualifies_pinned_schema_and_owner_grants")
        (selection, source_root, graph, adapter, row, task, policy,
         seed, each, profile) = source_case._case()
        features = source_features(release=REAL_RELEASE)
        with TemporaryDirectory() as directory:
            run_dir = Path(directory)
            with (genesis_feature_source_patch(features), host_source_authority_patch(),
                  patch.dict(os.environ, {
                      "BILQIS_DATA_PLANE": str(run_dir / "plane.sqlite3")}),
                  patch.object(helpers, "DECLARED", fixture.declared),
                  fixture._shape_patches(growth=True)):
                authority = issue_feature_authority(features)
                publish_genesis(run_dir, foundation_features=authority)
                parent0 = load_accepted_generation(run_dir)
                fixture.parent, fixture.extents = parent0.retained_state, parent0.extents

                fake = _seed_full_page_continuation(parent0)
                with patch(
                        "bilqis_mlx.runtime.bamf_bundle.source_continuation."
                        "_require_source_qualified_continuation", return_value=fake):
                    seed_staged = stage_source_qualified_motif_allocation(
                        run_dir, fixture._step(), fake)
                    _publish_staged(run_dir, parent0, seed_staged)
                parent = load_accepted_generation(run_dir)
                self.assertEqual(len(parent.retained_state.allocations.manifest.slots), 16384)

                fixture.parent, fixture.extents = parent.retained_state, parent.extents
                transaction = fixture._step()
                continuation, _frontier = seal_source_qualified_motifs_from_bundle(
                    adapter, row, selection,
                    retained_bundle_root=(run_dir / "bamf-bundles"
                                          / parent.retained_state.custody.manifest_sha256),
                    expected_manifest_sha256=parent.retained_state.custody.manifest_sha256,
                    source_root=source_root, graph=graph, task_scope=task,
                    source_frontier=SourceFrontier(1, 1, ()), policy=policy,
                    source_seed=seed, source_each=each,
                    budget=MotifBudget(64, page_growth_bytes=MOTIF_PAGE_STATE_BYTES),
                    source_profile_parameters=profile)
                staged = stage_source_qualified_motif_allocation(
                    run_dir, transaction, continuation)
                retained, successor, pointer = _publish_staged(run_dir, parent, staged)
                cold = load_accepted_generation(run_dir)
                continued, _frontier = continue_source_qualified_motifs_from_bundle(
                    adapter, row, selection,
                    retained_bundle_root=(run_dir / "bamf-bundles"
                                          / pointer["manifest_sha256"]),
                    expected_manifest_sha256=pointer["manifest_sha256"],
                    source_root=source_root, graph=graph, task_scope=task,
                    source_frontier=SourceFrontier(1, 1, ()), policy=policy,
                    source_seed=seed, source_each=each,
                    budget=MotifBudget(64, page_growth_bytes=MOTIF_PAGE_STATE_BYTES),
                    source_profile_parameters=profile)

        self.assertEqual(parent.extents.motif_page_count, 1)
        self.assertEqual(successor.transition.added_pages, 1)
        self.assertEqual(successor.extents.motif_page_count, 2)
        self.assertEqual(cold.extents, successor.extents)
        self.assertEqual(cold.retained_state.allocations, retained.allocations)
        np.testing.assert_array_equal(
            np.asarray(cold.retained_state.optimizer.parameters[MOTIF]),
            np.asarray(parent.retained_state.optimizer.parameters[MOTIF]))
        np.testing.assert_array_equal(
            np.asarray(cold.retained_state.optimizer.parameters["motif.page.1"]),
            np.asarray(retained.optimizer.parameters["motif.page.1"]))
        for tree in ("m", "v", "update_counts"):
            np.testing.assert_array_equal(
                np.asarray(getattr(cold.retained_state.optimizer, tree)[MOTIF]),
                np.asarray(getattr(parent.retained_state.optimizer, tree)[MOTIF]))
            np.testing.assert_array_equal(
                np.asarray(getattr(cold.retained_state.optimizer, tree)["motif.page.1"]),
                np.asarray(getattr(retained.optimizer, tree)["motif.page.1"]))
            self.assertFalse(np.asarray(
                getattr(cold.retained_state.optimizer, tree)["motif.page.1"]).any())
        self.assertEqual(continued.candidate.view.plan.allocated, ())
        self.assertEqual(continued.candidate.proposed.manifest.slots,
                         retained.allocations.manifest.slots)


if __name__ == "__main__":
    unittest.main()
