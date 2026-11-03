"""Literal source, closure and sidecar accounting."""
from unittest import TestCase

from bilqis_mlx.semantics.frame_compiler import compile_prefix
from bilqis_mlx.semantics.tests.frame_compiler.fixtures import RELEASE, _case


class CompileStatsTests(TestCase):
    def test_partial_and_closed_prefix_have_literal_accounting(self):
        ast, config = _case()
        before = compile_prefix(ast, 7, RELEASE, config).stats
        after = compile_prefix(ast, 8, RELEASE, config).stats
        self.assertEqual(
            (before.actual_atoms, before.actual_frames,
             before.neural_positions, before.sidecar_bytes), (7, 0, 7, 0))
        self.assertEqual(
            (after.actual_atoms, after.actual_frames,
             after.neural_positions, after.sidecar_bytes), (8, 1, 9, 2563))
        self.assertEqual(after.disposition_shares, (
            ("COMPACT", 1, 1), ("EXTENDED", 0, 1), ("ATOMIC", 0, 1)))
