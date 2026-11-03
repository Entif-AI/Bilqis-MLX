"""Reject accidental loss of reviewed successor behavior during #641 intake."""
import unittest

from verify_current_integration import ANCHOR, IDENTITY, OWNER, require_overlay


class CurrentIntegrationTests(unittest.TestCase):
    def test_only_public_factory_metadata_can_change(self):
        before = 'source_authority = True\n' + ANCHOR
        require_overlay(OWNER, before, before + IDENTITY)
        with self.assertRaisesRegex(ValueError, 'unexpected integration delta'):
            require_overlay(OWNER, before, before.replace('True', 'False') + IDENTITY)

    def test_unrelated_owner_cannot_change(self):
        with self.assertRaisesRegex(ValueError, 'unexpected integration delta'):
            require_overlay('bilqis_mlx/runtime/_depth/block_attnres.py', 'accepted', 'old')

    def test_metadata_fix_cannot_be_omitted(self):
        with self.assertRaisesRegex(ValueError, 'unexpected integration delta'):
            require_overlay(OWNER, ANCHOR, ANCHOR)

    def test_missing_baseline_anchor_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'unexpected factory metadata baseline'):
            require_overlay(OWNER, 'unknown source', 'unknown source')


if __name__ == '__main__':
    unittest.main()
