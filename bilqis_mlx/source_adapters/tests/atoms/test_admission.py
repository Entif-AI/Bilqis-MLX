"""Positive source-owned identities and immutable prefix authority."""
from dataclasses import replace
from unittest import TestCase, skipUnless

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_compiler import compile_prefix
from bilqis_mlx.semantics.source_atom_binding import AtomBindingDisposition
from bilqis_mlx.source_adapters.atoms.admission import public_formal_atom_context
from bilqis_mlx.source_adapters.atom_binding import (
    build_source_atom_handoff, require_pinned_embedding_ready,
)
from bilqis_mlx.source_adapters.copular import SYMBOL
from .helpers import REAL_BUNDLE, source_case


@skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class AdmissionTests(TestCase):
    def test_actual_source_row_owns_every_atom_and_the_complete_operator_signature(self):
        ast, config, compiled, handoff, selection, row, graph, args = source_case()
        self.assertTrue(handoff.embedding_ready)
        self.assertEqual(tuple(b.disposition for b in handoff.bindings),
                         (AtomBindingDisposition.BOUND,) * len(ast.atoms))
        coordinates = require_pinned_embedding_ready(
            handoff, compiled, config, selection, row, graph, **args)
        self.assertEqual(tuple(index for index, _ in coordinates), tuple(row["tokens"]))
        operator = next(b for b in handoff.bindings if b.token == SYMBOL)
        self.assertEqual(operator.candidate_abi_index, 227)
        self.assertEqual(operator.candidate_semantic_id,
                         "ithkuil:LEXSENSE-5286ade9db42c7/finite-reference-identity/v1")
        self.assertEqual(operator.candidate_type_ids, ("Entity*Entity->Boolean",))
        self.assertNotIn("Boolean", operator.candidate_type_ids)

    def test_later_prefix_preserves_earlier_bindings_and_mints_no_future_grant(self):
        ast, config, compiled, early, selection, row, graph, args = source_case(visible_end=1)
        self.assertEqual(tuple(g.source_handle for g in config.frontier.grants),
                         (ast.atoms[0].source_reference,))
        later_task = replace(config.task, causal_prefix_end=len(ast.atoms))
        later_ast, later_config = public_formal_atom_context(
            selection, row, graph, task=later_task, frontier=config.frontier,
            policy=config.policy, **args)
        later_compiled = compile_prefix(later_ast, len(ast.atoms), early.semantic_release, later_config)
        later = build_source_atom_handoff(
            later_compiled, later_config, selection, row, graph, **args)
        self.assertEqual(later.bindings[0], early.bindings[0])
        self.assertEqual(len(early.bindings), 1)
        self.assertTrue(later.embedding_ready)

    def test_repeated_source_admission_is_idempotent(self):
        ast, config, _, _, selection, row, graph, args = source_case()
        next_ast, next_config = public_formal_atom_context(
            selection, row, graph, task=config.task, frontier=config.frontier,
            policy=config.policy, **args)
        self.assertEqual(next_ast, ast)
        self.assertEqual(next_config, config)

    def test_grant_collision_cannot_erase_revocation_or_stale_correction(self):
        _, config, _, _, selection, row, graph, args = source_case()
        for replacement in (replace(config.frontier.grants[0], revoked=True),
                            replace(config.frontier.grants[0], correction_generation=0)):
            frontier = replace(config.frontier, grants=(replacement, *config.frontier.grants[1:]))
            with self.assertRaises(BilqisError):
                public_formal_atom_context(
                    selection, row, graph, task=config.task, frontier=frontier,
                    policy=config.policy, **args)
            self.assertEqual(frontier.grants[0], replacement)
