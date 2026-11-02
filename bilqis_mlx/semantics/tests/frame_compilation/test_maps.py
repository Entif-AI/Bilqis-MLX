"""Maps compiler regressions."""
import unittest
from bilqis_mlx.semantics.tests.frame_compilation.helpers import (PackDisposition, PositionKind, RELEASE, SourceSpan, _case, compile_prefix, patch, reconstruct, socket)


class MapsTests(unittest.TestCase):
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

    def test_every_four_member_prefix_preserves_only_visible_atoms(self):
        ast, config = _case()
        with patch.object(
            socket, "socket", side_effect=AssertionError("network")
        ):
            for prefix in range(9):
                compiled = compile_prefix(ast, prefix, RELEASE, config)
                visible = reconstruct(compiled)
                self.assertEqual(visible.atoms, ast.atoms[:prefix])
                self.assertEqual(
                    len(visible.frames), 1 if prefix == 8 else 0)
                closures = tuple(
                    position for position in compiled.positions
                    if position.kind is PositionKind.CLOSURE)
                self.assertEqual(len(closures), 1 if prefix == 8 else 0)
                if prefix < 8:
                    self.assertEqual(len(compiled.positions), prefix)
                    self.assertIsNone(compiled.context_digest)
                    self.assertFalse(any(
                        position.frame_handle for position
                        in compiled.positions))
                else:
                    self.assertEqual(
                        closures[0].packed.disposition,
                        PackDisposition.COMPACT)
                    self.assertEqual(
                        visible.frames, ast.frames)
