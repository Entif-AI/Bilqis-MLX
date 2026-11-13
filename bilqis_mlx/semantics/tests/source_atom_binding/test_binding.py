"""Immutable single-atom record integrity."""
from dataclasses import replace
from unittest import TestCase

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.source_atom_binding import _resolve_visible_atoms
from .helpers import case, snapshot, witness


class BindingTests(TestCase):
    def test_forged_binding_abi_type_release_and_bundle_are_rejected(self):
        tokens = ("alpha", "beta")
        _, config, compiled = case(tokens)
        first = _resolve_visible_atoms(
            compiled, config, snapshot(tokens), witness(tokens),
            {"tokens": list(tokens)}).bindings[0]
        for field, value in (
                ("candidate_abi_index", 99),
                ("candidate_type_ids", ("Forged",)),
                ("semantic_release", "9" * 64),
                ("a01_bundle_id", "8" * 64)):
            with self.subTest(field=field), self.assertRaises(BilqisError):
                replace(first, **{field: value})
