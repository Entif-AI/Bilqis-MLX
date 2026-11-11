"""Pinned source motifs continue through the actual CAS bundle reader.

The numerical body is the existing tiny B13 fixture, not an admitted learner.
Motif identities and source replay use the externally pinned A01 artifact.
"""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning._engram.tests.test_atlas_engram_source import SourceQualifiedMotifTests
from bilqis_mlx.learning.atlas_engram import MotifBudget
from bilqis_mlx.runtime import mlx_checkpoint
import bilqis_mlx.runtime.bamf_bundle.motif.source_continuation as continuation
import bilqis_mlx.learning._atlas_candidate.motif_transition as b12_transition
import bilqis_mlx.runtime.bamf_bundle.motif.transition as b13_transition
from bilqis_mlx.runtime.bamf_bundle import (
    continue_source_qualified_motifs_from_bundle, load_bamf_bundle, save_bamf_bundle,
)
from bilqis_mlx.runtime.bamf_bundle.motif.source_continuation import (
    SourceQualifiedMotifContinuation, stage_source_qualified_motif_allocation,
)
from bilqis_mlx.semantics.context_eligibility import SourceFrontier
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, next_accepted_step, parent_state, rewrite_motif_bundle_fixture,
    shape_patch,
)


@unittest.skipUnless(os.environ.get('BILQIS_ATLAS_REAL_ARTIFACT'),
                     'real repo-pinned A01 artifact required')
class MotifSourceContinuationTests(unittest.TestCase):
    def test_caller_cannot_mint_source_continuation(self):
        self.assertFalse(hasattr(continuation, "_issue_continuation"))
        self.assertFalse(hasattr(continuation, "_CONTINUATION_ISSUER"))
        source = SourceQualifiedMotifTests(
            "test_real_source_replay_qualifies_pinned_schema_and_owner_grants")
        approved, _frontier = source._prepare()
        forged = object.__new__(SourceQualifiedMotifContinuation)
        for name, value in (
                ("approved", approved), ("parent_manifest_sha256", "1" * 64),
                ("parent_extents_sha256", "2" * 64),
                ("parent_allocation_sha256", "3" * 64)):
            object.__setattr__(forged, name, value)
        with self.assertRaises(BilqisError):
            stage_source_qualified_motif_allocation("unused", None, forged)

    def test_transition_authority_exposes_no_raw_mint_or_issuer_token(self):
        for module, forbidden in (
                (b12_transition, (
                    "_ISSUER", "_raw_issue_transition",
                    "_issue_candidate_motif_allocation_transition")),
                (b13_transition, (
                    "_ISSUER", "_raw_issue_transition",
                    "_issue_motif_allocation_transition"))):
            for name in forbidden:
                self.assertFalse(hasattr(module, name), name)

    def test_continuation_requires_external_exact_manifest_digest(self):
        for invalid_digest in (None, "", "A" * 64, "0" * 63, "g" * 64):
            with self.subTest(invalid_digest=invalid_digest):
                with patch.object(continuation, "load_bamf_bundle") as load:
                    with self.assertRaises(BilqisError):
                        continue_source_qualified_motifs_from_bundle(
                            None, None, None,
                            retained_bundle_root="unused",
                            expected_manifest_sha256=invalid_digest,
                            source_root=None, graph=None, task_scope=None,
                            source_frontier=None, policy=None, source_seed=0,
                            source_each=0, budget=None,
                        )
                    load.assert_not_called()

    def test_cas_read_and_next_update_preserve_source_motif_slots_and_use_priority(self):
        source = SourceQualifiedMotifTests(
            'test_real_source_replay_qualifies_pinned_schema_and_owner_grants')
        first, _ = source._prepare()
        allocations = first.candidate.proposed
        self.assertTrue(allocations.manifest.slots)
        parent = parent_state()
        (selection, source_root, graph, adapter, row, task, policy,
         seed, each, profile) = source._case()
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (patch.dict(os.environ, {'BILQIS_DATA_PLANE': str(root / 'plane.sqlite3')}),
                  shape_patch(), patch.object(mlx_checkpoint, 'assert_headroom')):
                bundle0 = root / 'bundle-0'
                manifest = save_bamf_bundle(
                    candidate(parent), bundle0, reserve_gib=0.)
                manifest = rewrite_motif_bundle_fixture(bundle0, manifest, allocations)
                self.assertIn('object_sha256', manifest['tensors'])
                self.assertFalse((bundle0 / manifest['tensors']['filename']).exists())
                loaded = load_bamf_bundle(
                    bundle0, expected_manifest_sha256=manifest['manifest_sha256'])
                self.assertEqual(loaded.retained_state.allocations, allocations)
                continued = next_accepted_step(loaded.retained_state, loaded.extents)
                self.assertEqual(continued.optimizer_step, parent.optimizer_step + 1)
                self.assertEqual(continued.allocations, allocations)
                bundle1 = root / 'bundle-1'
                resumed_manifest = save_bamf_bundle(
                    candidate(
                        continued, generation=1,
                        parent=manifest['manifest_sha256'],
                    ),
                    bundle1, reserve_gib=0.,
                )
                second, _ = continue_source_qualified_motifs_from_bundle(
                    adapter, row, selection,
                    retained_bundle_root=bundle1,
                    expected_manifest_sha256=resumed_manifest['manifest_sha256'],
                    source_root=source_root, graph=graph, task_scope=task,
                    source_frontier=SourceFrontier(1, 1, ()), policy=policy,
                    source_seed=seed, source_each=each, budget=MotifBudget(64),
                    source_profile_parameters=profile,
                )
        self.assertEqual(second.candidate.view.plan.allocated, ())
        self.assertEqual(second.candidate.proposed.manifest.slots,
                         allocations.manifest.slots)
        original_uses = dict(allocations.observed_uses)
        continued_uses = dict(second.candidate.proposed.observed_uses)
        self.assertEqual(set(continued_uses), set(original_uses))
        self.assertTrue(all(continued_uses[key] > count
                            for key, count in original_uses.items()))


if __name__ == '__main__':
    unittest.main()
