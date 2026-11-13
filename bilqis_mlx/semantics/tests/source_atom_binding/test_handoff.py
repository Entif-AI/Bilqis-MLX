"""Whole-prefix order, duplicate and future-boundary rejection."""
from dataclasses import replace
from unittest import TestCase

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.source_atom_binding import _resolve_visible_atoms
from .helpers import case, snapshot, witness


class HandoffTests(TestCase):
    def test_duplicate_and_future_atom_are_rejected(self):
        tokens = ("alpha", "beta")
        _, config, compiled = case(tokens)
        handoff = _resolve_visible_atoms(
            compiled, config, snapshot(tokens), witness(tokens), {"tokens": list(tokens)})
        with self.assertRaises(BilqisError):
            replace(handoff, bindings=(handoff.bindings[0], handoff.bindings[0]))
        with self.assertRaises(BilqisError):
            replace(handoff, visible_end=3,
                    bindings=(*handoff.bindings, handoff.bindings[-1]))
