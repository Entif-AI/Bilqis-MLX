"""Candidate resolution, prefix stability and current rights checks."""
from dataclasses import replace
from unittest import TestCase

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_compiler import atom_evidence_digest, compile_prefix
from bilqis_mlx.semantics.source_atom_binding import (
    AtomBindingDisposition, SourceRowWitness, _resolve_visible_atoms,
    require_embedding_ready,
)
from .helpers import RELEASE, case, snapshot, witness


class ResolutionTests(TestCase):
    def test_candidate_is_explicitly_held_without_raw_source_reference_law(self):
        tokens = ("alpha", "beta")
        _, config, compiled = case(tokens)
        handoff = _resolve_visible_atoms(
            compiled, config, snapshot(tokens), witness(tokens), {"tokens": list(tokens)})
        self.assertEqual(len(handoff.bindings), 2)
        first = handoff.bindings[0]
        self.assertEqual(first.candidate_abi_index, 0)
        self.assertEqual(first.candidate_semantic_id, "semantic:alpha")
        self.assertEqual(first.disposition, AtomBindingDisposition.SOURCE_HELD)
        self.assertIn("SOURCE_ATOM_REFERENCE_AUTHORITY_UNAVAILABLE", first.reason_codes)
        self.assertIn("SOURCE_ATOM_INSTANCE_AUTHORITY_UNAVAILABLE", first.reason_codes)
        self.assertIn("SOURCE_ATOM_TYPE_AUTHORITY_UNAVAILABLE", first.reason_codes)
        with self.assertRaises(BilqisError) as caught:
            require_embedding_ready(handoff, compiled, config, snapshot(tokens),
                                    witness(tokens), {"tokens": list(tokens)})
        self.assertEqual(caught.exception.context["reason"], "BAMF_SOURCE_ATOM_BINDING_HELD")

    def test_binding_digest_is_prefix_stable_and_future_atom_is_absent(self):
        tokens = ("alpha", "beta", "gamma")
        _, config, prefix = case(tokens, visible_end=1)
        _, _, full = case(tokens, visible_end=3)
        early_config = replace(config, task=replace(config.task, causal_prefix_end=1))
        early = _resolve_visible_atoms(
            prefix, early_config, snapshot(tokens), witness(tokens), {"tokens": list(tokens)})
        later = _resolve_visible_atoms(
            full, config, snapshot(tokens), witness(tokens), {"tokens": list(tokens)})
        self.assertEqual(early.bindings[0], later.bindings[0])
        self.assertEqual(early.bindings[0].binding_digest, later.bindings[0].binding_digest)
        self.assertEqual(tuple(item.atom_index for item in early.bindings), (0,))
        self.assertEqual(tuple(item.atom_index for item in later.bindings), (0, 1, 2))

    def test_wrong_token_or_row_index_never_becomes_an_abi_binding(self):
        tokens = ("alpha", "beta")
        ast, config, _ = case(tokens)
        changed = replace(ast, atoms=(replace(ast.atoms[0], token="beta"), ast.atoms[1]))
        grants = tuple(replace(
            grant, evidence_digest=atom_evidence_digest(changed.source_instance_id, atom, RELEASE))
            for grant, atom in zip(config.frontier.grants, changed.atoms))
        changed_config = replace(config, frontier=replace(config.frontier, grants=grants))
        compiled = compile_prefix(changed, 2, RELEASE, changed_config)
        handoff = _resolve_visible_atoms(
            compiled, changed_config, snapshot(tokens), witness(tokens), {"tokens": list(tokens)})
        self.assertEqual(handoff.bindings[0].disposition, AtomBindingDisposition.UNMAPPED)
        self.assertIn("SOURCE_ATOM_ROW_TOKEN_MISMATCH", handoff.bindings[0].reason_codes)
        shifted = SourceRowWitness(
            "source.fixture/v1", "fixture.generator/v1", "fixture.oracle/v1",
            "fixture.capability", "fixture:sense", (1, 0))
        handoff = _resolve_visible_atoms(
            compile_prefix(ast, 2, RELEASE, config), config, snapshot(tokens),
            shifted, {"tokens": list(tokens)})
        self.assertEqual(handoff.bindings[0].disposition, AtomBindingDisposition.UNMAPPED)
        self.assertIn("SOURCE_ATOM_ROW_TOKEN_MISMATCH", handoff.bindings[0].reason_codes)

    def test_revocation_stale_correction_and_reference_change_hold_and_rekey(self):
        tokens = ("alpha",)
        ast, config, compiled = case(tokens)
        args = snapshot(tokens), witness(tokens), {"tokens": list(tokens)}
        base = _resolve_visible_atoms(compiled, config, *args).bindings[0]
        revoked_grant = replace(config.frontier.grants[0], revoked=True)
        revoked = replace(config, frontier=replace(config.frontier, grants=(revoked_grant,)))
        changed = _resolve_visible_atoms(compiled, revoked, *args).bindings[0]
        self.assertIn("SOURCE_ATOM_CURRENT_RIGHTS_HELD", changed.reason_codes)
        self.assertNotEqual(changed.binding_digest, base.binding_digest)
        stale = replace(config, frontier=replace(config.frontier, correction_generation=2))
        changed = _resolve_visible_atoms(compiled, stale, *args).bindings[0]
        self.assertIn("SOURCE_ATOM_CURRENT_RIGHTS_HELD", changed.reason_codes)
        self.assertNotEqual(changed.binding_digest, base.binding_digest)
        changed_atom = replace(ast.atoms[0], source_reference="forged:atom:0")
        changed_ast = replace(ast, atoms=(changed_atom,))
        forged_grant = replace(
            config.frontier.grants[0], source_handle=changed_atom.source_reference,
            evidence_digest=atom_evidence_digest(changed_ast.source_instance_id, changed_atom, RELEASE))
        forged_config = replace(config, frontier=replace(config.frontier, grants=(forged_grant,)))
        forged_compiled = compile_prefix(changed_ast, 1, RELEASE, forged_config)
        changed = _resolve_visible_atoms(forged_compiled, forged_config, *args).bindings[0]
        self.assertEqual(changed.disposition, AtomBindingDisposition.SOURCE_HELD)
        self.assertIn("SOURCE_ATOM_REFERENCE_AUTHORITY_UNAVAILABLE", changed.reason_codes)
        self.assertNotEqual(changed.binding_digest, base.binding_digest)
