"""B03.3 preserves source-owned nesting and padding-free compiler counts."""
import unittest

import mlx.core as mx

from bilqis_mlx.learning.frame_encoder import encode_frames
from bilqis_mlx.learning.tests.frames.nested_fixtures import _case
from bilqis_mlx.semantics.frame_compiler import PositionKind


class NestedObservabilityTests(unittest.TestCase):
    def test_nested_source_parent_scope_and_constituent_handles_are_exact(self):
        ast, _, compiled, vectors, parameters = _case()
        encoded = encode_frames(compiled, vectors, parameters)
        parent_tree, atomic_tree = ast.frames
        frames = (
            parent_tree.children[0].root, atomic_tree.root, parent_tree.root)
        positions = tuple(
            p for p in encoded.handles[1]
            if p is not None and p.kind is PositionKind.CLOSURE)
        self.assertEqual(
            tuple(p.frame_handle for p in positions),
            ("frame:mixed:0", "frame:mixed:1", "frame:mixed:2"))
        for position, frame, scope in zip(
                positions, frames, ("fixture", "synthetic:public", "fixture")):
            with self.subTest(frame=position.frame_handle):
                sidecar = position.packed.sidecar
                self.assertEqual(sidecar.source_instance_id, frame.source_instance_id)
                self.assertEqual(sidecar.source_span, frame.source_span)
                self.assertEqual(sidecar.structural_path, frame.structural_path)
                self.assertEqual(sidecar.occurrence_id, frame.occurrence_id)
                self.assertEqual(sidecar.content_digest, frame.content_digest)
                self.assertEqual(sidecar.parent_occurrence_id, frame.parent_occurrence_id)
                self.assertEqual(sidecar.causal_prefix_end, frame.causal_prefix_end)
                scopes = tuple(
                    s for s in encoded.compiled.rows[1].maps.scope_boundaries
                    if s.frame_handle == position.frame_handle)
                self.assertEqual(len(scopes), 1)
                self.assertEqual(scopes[0].scope, scope)
                if position.frame_handle == "frame:mixed:1":
                    self.assertIsNone(sidecar.scope)
                else:
                    self.assertEqual(scopes[0].scope, sidecar.scope)
        child, _, parent = (p.packed.sidecar for p in positions)
        self.assertEqual(child.parent_occurrence_id, parent.occurrence_id)
        binding = parent.constituents[0]
        self.assertEqual((binding.role_id, binding.occurrence_index), ("child", 0))
        self.assertEqual(binding.child_occurrence_id, child.occurrence_id)
        self.assertEqual(binding.child_content_digest, child.content_digest)
        self.assertEqual(binding.child_type_ids, ("Frame",))
        self.assertEqual(binding.semantic_ids, ())
        self.assertEqual(binding.abi_indices, ())
        early = tuple(p for p in encoded.handles[0] if p is not None)
        self.assertEqual(early[-1].packed.sidecar, child)
        self.assertNotIn(parent.occurrence_id, tuple(
            p.packed.sidecar.occurrence_id for p in early if p.packed))

    def test_frame_and_fallback_counts_are_compiler_owned_and_ignore_padding(self):
        _, _, compiled, vectors, parameters = _case()
        encoded = encode_frames(compiled, vectors, parameters)
        self.assertIs(encoded.compiled, compiled.compiled)
        self.assertIs(encoded.handles, compiled.compiled.padded_positions)
        expected = (
            (4, 1, 5, (("COMPACT", 0, 1), ("EXTENDED", 1, 1), ("ATOMIC", 0, 1))),
            (8, 3, 11, (("COMPACT", 0, 3), ("EXTENDED", 2, 3), ("ATOMIC", 1, 3))),
        )
        for row, values in zip(encoded.compiled.rows, expected):
            with self.subTest(prefix=row.visible_end):
                stats = row.stats
                self.assertEqual((stats.actual_atoms, stats.actual_frames,
                                  stats.neural_positions, stats.disposition_shares), values)
                self.assertEqual(stats.neural_positions, len(row.positions))
                self.assertGreater(stats.sidecar_bytes, 0)
        self.assertEqual(encoded.global_seeds.shape, (2, 11, 768))
        self.assertTrue(all(p is None for p in encoded.handles[0][5:]))
        self.assertTrue(bool(mx.all(encoded.global_seeds[0, 5:] == 0)))
        self.assertEqual(tuple(
            p.packed.reason.value for p in encoded.handles[1] if p is not None and p.packed),
            ("SCHEMA_NOT_FOUR_SINGULAR_ROLES", "ATOMIC_FRAME",
             "SCHEMA_NOT_FOUR_SINGULAR_ROLES"))
