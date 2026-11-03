"""Pinned source motifs continue through the actual CAS bundle reader.

The numerical body is the existing tiny B13 fixture, not an admitted learner.
Motif identities and source replay use the externally pinned A01 artifact.
"""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.learning._engram.tests.test_atlas_engram_source import SourceQualifiedMotifTests
from bilqis_mlx.learning.atlas_candidate import _issue_retained_state
from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.bamf_bundle import load_bamf_bundle, save_bamf_bundle
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, next_accepted_step, parent_state, shape_patch,
)


@unittest.skipUnless(os.environ.get('BILQIS_ATLAS_REAL_ARTIFACT'),
                     'real repo-pinned A01 artifact required')
class MotifSourceContinuationTests(unittest.TestCase):
    def test_cas_read_and_next_update_preserve_source_motif_slots_and_use_priority(self):
        source = SourceQualifiedMotifTests(
            'test_source_qualified_continuation_preserves_retained_slots_and_priority')
        first, _ = source._prepare()
        allocations = first.candidate.proposed
        self.assertTrue(allocations.manifest.slots)
        parent = parent_state()
        retained = _issue_retained_state(
            parent.optimizer, parent.policy, allocations, parent.optimizer_step)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (patch.dict(os.environ, {'BILQIS_DATA_PLANE': str(root / 'plane.sqlite3')}),
                  shape_patch(), patch.object(mlx_checkpoint, 'assert_headroom')):
                manifest = save_bamf_bundle(candidate(retained), root / 'bundle')
                self.assertIn('object_sha256', manifest['tensors'])
                self.assertFalse((root / 'bundle' / manifest['tensors']['filename']).exists())
                loaded = load_bamf_bundle(
                    root / 'bundle', expected_manifest_sha256=manifest['manifest_sha256'])
                self.assertEqual(loaded.retained_state.allocations, allocations)
                continued = next_accepted_step(loaded.retained_state)
                self.assertEqual(continued.optimizer_step, retained.optimizer_step + 1)
                self.assertEqual(continued.allocations, allocations)
                second, _ = source._prepare(retained_state=continued)
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
