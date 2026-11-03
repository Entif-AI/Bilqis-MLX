"""Frame compiler: positions contracts."""
from __future__ import annotations
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_codec import _canonical_bytes
from bilqis_mlx.semantics.frame_compiler import PositionKind, SourceAtom, compile_prefix
from bilqis_mlx.semantics.tests.frame_compiler.fixtures import (
    RELEASE, _case, _with_atom_grants,
)


class PositionsTests(TestCase):
    def test_compact_frame_sidecar_matches_literal_canonical_wire_bytes(self):
        ast, config = _case()
        compiled = compile_prefix(ast, 8, RELEASE, config)
        closure = next(
            item for item in compiled.positions
            if item.kind is PositionKind.CLOSURE)
        actual = _canonical_bytes(asdict(closure.packed.sidecar))
        literal = (
            Path(__file__).parent.parent / "fixtures" / "a05_quad_sidecar.json"
        ).read_bytes()
        self.assertEqual(len(literal), 2563)
        self.assertEqual(
            sha256(literal).hexdigest(),
            "cd2485f302d7e05bea293493e7f697315763fbf0cc8c0df4dbbe99167a7e43fc")
        self.assertEqual(actual, literal)


    def test_overflow_fails_before_packing_or_padding(self):
        ast, config = _case()
        extended = replace(
            ast, atoms=ast.atoms + tuple(
                SourceAtom(i, f"extra:{i}", f"source:extra:{i}")
                for i in range(8, 1024)))
        expanded_config = replace(
            config, task=replace(
                config.task, causal_prefix_end=1024))
        with patch(
            "bilqis_mlx.semantics.frame_compiler.pack_frame",
            side_effect=AssertionError("packed before length guard"),
        ):
            with self.assertRaises(BilqisError) as caught:
                compile_prefix(
                    extended, 1024, RELEASE, expanded_config)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_NEURAL_LENGTH_EXCEEDED")
        atoms_only = replace(
            extended, frames=(), atoms=extended.atoms + (
                SourceAtom(1024, "extra:1024", "source:extra:1024"),))
        with self.assertRaises(BilqisError):
            compile_prefix(
                atoms_only, 1025, RELEASE, replace(
                    expanded_config, approved=None,
                    task=replace(
                        expanded_config.task, causal_prefix_end=1025)))


    def test_exact_1024_neural_positions_are_admitted(self):
        ast, config = _case()
        expanded = replace(
            ast, atoms=ast.atoms + tuple(
                SourceAtom(i, f"extra:{i}", f"source:extra:{i}")
                for i in range(8, 1024)))
        full_config = replace(
            config, task=replace(
                config.task, causal_prefix_end=1024))
        full_config = _with_atom_grants(expanded, full_config)
        atoms_only = compile_prefix(
            replace(expanded, frames=()), 1024, RELEASE,
            replace(full_config, approved=None))
        self.assertEqual(len(atoms_only.positions), 1024)
        self.assertEqual(atoms_only.stats.actual_atoms, 1024)
        self.assertEqual(atoms_only.stats.actual_frames, 0)
        one_frame = compile_prefix(
            replace(expanded, atoms=expanded.atoms[:1023]),
            1023, RELEASE, replace(
                full_config, task=replace(
                    full_config.task, causal_prefix_end=1023)))
        self.assertEqual(len(one_frame.positions), 1024)
        self.assertEqual(
            (one_frame.stats.actual_atoms,
             one_frame.stats.actual_frames), (1023, 1))
