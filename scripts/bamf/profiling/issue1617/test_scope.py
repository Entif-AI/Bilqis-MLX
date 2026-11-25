"""Dependency-boundary tests for the disposable preparation experiment."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from scripts.bamf.detached.support import _tree_digest
from scripts.bamf.profiling.issue1617.scope import PreparedOwner


def context():
    return SimpleNamespace(release=object(), graph={}, source_root=Path('source'),
                           source_registry=object())


class PreparedScopeTests(unittest.TestCase):
    def test_same_context_reuses_and_replacement_invalidates(self):
        current = context()
        owner = PreparedOwner(current)
        self.assertTrue(owner.matches(current))
        self.assertFalse(owner.matches(SimpleNamespace(**vars(current))))
        for name, value in (
                ('release', object()), ('graph', {}),
                ('source_root', Path('changed-source')),
                ('source_registry', object())):
            with self.subTest(dependency=name):
                current = context()
                owner = PreparedOwner(current)
                setattr(current, name, value)
                self.assertFalse(owner.matches(current))

    def test_pinned_experiment_identity_changes_with_provider_or_operator_bytes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = tuple(root / name for name in ('provider.py', 'operator.py', 'source.json'))
            for path in paths:
                path.write_text('original\n')
            original = _tree_digest(root)
            self.assertEqual(_tree_digest(root), original)
            for path in paths:
                with self.subTest(path=path.name):
                    path.write_text('changed\n')
                    self.assertNotEqual(_tree_digest(root), original)
                    path.write_text('original\n')
                    self.assertEqual(_tree_digest(root), original)


if __name__ == '__main__':
    unittest.main()
