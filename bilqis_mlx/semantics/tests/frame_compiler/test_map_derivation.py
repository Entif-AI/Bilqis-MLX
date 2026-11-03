"""Frame compiler: maps contracts."""
from __future__ import annotations
from unittest import TestCase
from bilqis_mlx.semantics.frame_compiler import compile_prefix
from bilqis_mlx.semantics.frame_schema import SourceSpan
from bilqis_mlx.semantics.tests.frame_compiler.fixtures import (
    RELEASE, _case,
)


class MapsTests(TestCase):
    def test_exact_source_maps_role_access_expansion_and_prefix_ends(self):
        ast, config = _case()
        partial = compile_prefix(ast, 7, RELEASE, config).maps
        self.assertEqual(partial.prefix_ends, tuple(range(8)))
        self.assertEqual(partial.role_access, ())
        self.assertEqual(partial.expansion_handles, ())
        complete = compile_prefix(ast, 8, RELEASE, config)
        maps = complete.maps
        self.assertEqual(maps.prefix_ends, (
            0, 1, 2, 3, 4, 5, 6, 7, 9))
        self.assertEqual(len(maps.position_to_source), 9)
        self.assertEqual(
            tuple(item.source_reference
                  for item in maps.position_to_source[:8]),
            tuple(atom.source_reference for atom in ast.atoms))
        self.assertEqual(
            maps.position_to_source[8].source_span, SourceSpan(0, 8))
        self.assertEqual(
            maps.source_to_positions[0], (0, 8))
        self.assertEqual(
            maps.source_to_positions[7], (7, 8))
        self.assertEqual(maps.padding_mask, (True,) * 9)
        self.assertEqual(
            tuple(item.role_id for item in maps.role_access),
            ("slot0", "slot1", "slot2", "slot3"))
        self.assertEqual(
            tuple(item.abi_indices for item in maps.role_access),
            ((0,), (1,), (2,), (3,)))
        self.assertEqual(
            tuple(item.source_references for item in maps.role_access),
            tuple((f"source:entity:{i}",) for i in range(4)))
        self.assertEqual(
            maps.expansion_handles[0].frame_handle, "frame:quad:0")
        self.assertEqual(
            maps.scope_boundaries[0].end_position, 9)
        self.assertEqual(
            maps.scope_boundaries[1].scope, "fixture")
        self.assertEqual(
            (complete.stats.actual_atoms,
             complete.stats.actual_frames,
             complete.stats.neural_positions), (8, 1, 9))
        self.assertEqual(complete.stats.disposition_shares, (
            ("COMPACT", 1, 1), ("EXTENDED", 0, 1),
            ("ATOMIC", 0, 1)))
        self.assertGreater(complete.stats.sidecar_bytes, 0)
