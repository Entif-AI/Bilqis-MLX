"""Frame compiler: source contracts."""
from __future__ import annotations
from unittest import TestCase
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_compiler import compile_prefix
from bilqis_mlx.semantics.tests.frame_compiler.fixtures import (
    RELEASE, _case,
)


class SourceTests(TestCase):
    def test_foreign_release_or_prefix_is_rejected(self):
        ast, config = _case()
        for prefix, release in ((9, RELEASE), (8, "b" * 64), (-1, RELEASE)):
            with self.subTest(prefix=prefix, release=release):
                with self.assertRaises(BilqisError):
                    compile_prefix(ast, prefix, release, config)
