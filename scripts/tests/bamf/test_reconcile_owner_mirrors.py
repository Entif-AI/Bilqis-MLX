"""Literal behavior tests for source-preserving owner mirror reconciliation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.bamf.reconcile_owner_mirrors import additive_only, reconcile


def sha(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()


def fixture(root: Path) -> None:
    (root / 'issues').mkdir(parents=True)
    (root / 'children').mkdir()
    (root / 'issues/A03.md').write_text('alpha\nbeta\n')
    (root / 'workstack.json').write_text(json.dumps({'items': [
        {'key': 'A03', 'number': 349, 'body_sha256': sha('alpha\nbeta\n')}
    ]}))
    (root / 'children/registry.json').write_text(json.dumps({'entries': [
        {'key': 'A03.1', 'parent_key': 'A03',
         'source_parent_sha256': sha('alpha\nbeta\n')}
    ]}))


class OwnerMirrorReconciliationTests(unittest.TestCase):
    def test_additive_only_preserves_every_original_nonempty_line(self):
        self.assertTrue(additive_only('a\nb\n', 'a\nnew\nb\n'))
        self.assertFalse(additive_only('a\nb\n', 'a\nchanged\n'))
        self.assertFalse(additive_only('a\nb\n', 'b\na\n'))

    def test_dry_run_never_changes_files(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            before = (root / 'workstack.json').read_bytes()
            result = reconcile(root, ('A03',), lambda _: b'alpha\nnew\nbeta\n')
            self.assertFalse(result['applied'])
            self.assertEqual((root / 'workstack.json').read_bytes(), before)
            self.assertEqual((root / 'issues/A03.md').read_text(), 'alpha\nbeta\n')

    def test_apply_preserves_old_and_updates_both_hashes(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / 'repo'
            private = Path(temp) / 'private'
            fixture(root)
            new = b'alpha\nnew\nbeta\n'
            result = reconcile(root, ('A03',), lambda _: new,
                               apply=True, preserve=private)
            self.assertTrue(result['applied'])
            self.assertEqual((private / 'A03.before.md').read_text(), 'alpha\nbeta\n')
            self.assertEqual((root / 'issues/A03.md').read_bytes(), new)
            self.assertEqual(json.loads((root / 'workstack.json').read_text())
                             ['items'][0]['body_sha256'], sha(new.decode()))
            self.assertEqual(json.loads((root / 'children/registry.json').read_text())
                             ['entries'][0]['source_parent_sha256'], sha(new.decode()))
            again = reconcile(root, ('A03',), lambda _: new,
                              apply=True, preserve=private)
            self.assertEqual(again['owners'][0]['new_sha'], sha(new.decode()))

    def test_forged_local_mirror_is_rejected_without_mutation(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            (root / 'issues/A03.md').write_text('forged\n')
            with self.assertRaisesRegex(ValueError, 'LOCAL_OWNER_HASH_MISMATCH'):
                reconcile(root, ('A03',), lambda _: b'alpha\nnew\nbeta\n',
                          apply=True, preserve=root.parent / 'private')
            self.assertEqual((root / 'issues/A03.md').read_text(), 'forged\n')

    def test_non_additive_live_change_is_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            with self.assertRaisesRegex(ValueError, 'NON_ADDITIVE_LIVE_CHANGE'):
                reconcile(root, ('A03',), lambda _: b'alpha\nreplacement\n')


if __name__ == '__main__':
    unittest.main()
