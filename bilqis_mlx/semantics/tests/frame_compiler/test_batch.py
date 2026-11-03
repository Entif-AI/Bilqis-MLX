"""Frame compiler: batch contracts."""
from __future__ import annotations
from dataclasses import replace
from unittest import TestCase
from bilqis_mlx.semantics.frame_compiler import compile_prefix
from bilqis_mlx.semantics.tests.frame_compiler.fixtures import (
    RELEASE, _case,
)


class BatchTests(TestCase):
    def test_policy_version_changes_compiler_digest_even_without_frames(self):
        ast, config = _case()
        original = compile_prefix(ast, 7, RELEASE, config)
        changed = compile_prefix(
            ast, 7, RELEASE, replace(
                config, policy=replace(config.policy, policy_epoch=2)))
        self.assertNotEqual(original.cache_key, changed.cache_key)
        self.assertEqual(original.positions, changed.positions)
        self.assertEqual(original.policy_version[1], 1)
        self.assertEqual(changed.policy_version[1], 2)
