"""Reconstructed source authority rejects caller-controlled substitutions."""
from copy import deepcopy
from dataclasses import replace
from unittest import TestCase, skipUnless

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_compiler import atom_evidence_digest, compile_prefix
from bilqis_mlx.source_adapters.atom_binding import (
    build_source_atom_handoff, require_pinned_embedding_ready,
)
from .helpers import REAL_BUNDLE, source_case


@skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class SourceRevalidationTests(TestCase):
    def setUp(self):
        (self.ast, self.config, self.compiled, self.handoff, self.selection,
         self.row, self.graph, self.args) = source_case()

    def require(self, *, handoff=None, compiled=None, config=None,
                selection=None, row=None, graph=None, **args):
        return require_pinned_embedding_ready(
            self.handoff if handoff is None else handoff,
            self.compiled if compiled is None else compiled,
            self.config if config is None else config,
            self.selection if selection is None else selection,
            self.row if row is None else row,
            self.graph if graph is None else graph, **(self.args | args))

    def test_forged_token_graph_type_and_source_root_are_not_source_authority(self):
        changed = deepcopy(self.graph)
        changed["nodes"][self.row["tokens"][0]]["signature"] = "Forged->Boolean"
        with self.assertRaises(BilqisError):
            self.require(graph=changed)
        changed = deepcopy(self.graph)
        changed["tokens"][self.row["tokens"][0]] = "forged.token"
        with self.assertRaises(BilqisError):
            self.require(graph=changed)
        with self.assertRaises(BilqisError):
            self.require(source_root=self.args["source_root"] / "not-the-source-owner")

    def test_foreign_release_and_bundle_are_rejected(self):
        for field in ("release_sha256", "bundle_id", "source_bundle_id"):
            with self.subTest(field=field), self.assertRaises(BilqisError):
                self.require(selection=replace(self.selection, **{field: "9" * 64}))

    def test_unreproduced_source_row_and_unbounded_draw_are_rejected(self):
        row = deepcopy(self.row)
        row["tokens"] = list(reversed(row["tokens"]))
        with self.assertRaises(BilqisError):
            self.require(row=row)
        with self.assertRaises(BilqisError):
            self.require(source_each=129)
        with self.assertRaises(BilqisError):
            self.require(source_seed=18)

    def test_current_revocation_correction_and_policy_epoch_invalidate_handoff(self):
        revoked = replace(self.config.frontier.grants[0], revoked=True)
        changed = replace(self.config, frontier=replace(
            self.config.frontier, grants=(revoked, *self.config.frontier.grants[1:])))
        with self.assertRaises(BilqisError):
            self.require(config=changed)
        changed = replace(self.config, frontier=replace(
            self.config.frontier, correction_generation=2))
        with self.assertRaises(BilqisError):
            self.require(config=changed)
        with self.assertRaises(BilqisError):
            self.require(config=replace(self.config, policy=replace(self.config.policy, rights_epoch=2)))

    def test_future_visible_prefix_does_not_reuse_current_grants(self):
        changed = replace(self.config, task=replace(self.config.task, causal_prefix_end=1))
        with self.assertRaises(BilqisError):
            self.require(config=changed)

    def test_forged_instance_and_reference_remain_held_even_with_matching_caller_grants(self):
        variants = (
            replace(self.ast, source_instance_id="forged:instance"),
            replace(self.ast, atoms=(replace(self.ast.atoms[0], source_reference="forged:reference"),
                                    *self.ast.atoms[1:])),
        )
        by_reference = {grant.source_handle: grant for grant in self.config.frontier.grants}
        for ast in variants:
            grants = tuple(replace(
                by_reference[old.source_reference], source_handle=atom.source_reference,
                evidence_digest=atom_evidence_digest(ast.source_instance_id, atom, self.handoff.semantic_release))
                for old, atom in zip(self.ast.atoms, ast.atoms))
            config = replace(self.config, frontier=replace(
                self.config.frontier,
                grants=tuple(sorted(grants, key=lambda grant: grant.source_handle))))
            compiled = compile_prefix(ast, len(ast.atoms), self.handoff.semantic_release, config)
            handoff = build_source_atom_handoff(
                compiled, config, self.selection, self.row, self.graph, **self.args)
            self.assertFalse(handoff.embedding_ready)
            with self.assertRaises(BilqisError):
                self.require(handoff=handoff, compiled=compiled, config=config)

    def test_self_pinned_digest_cannot_replace_current_source_binding(self):
        from bilqis_mlx.semantics.source_atom_binding.binding import binding_projection
        from bilqis_mlx.semantics.source_atom_binding.handoff import handoff_projection
        from bilqis_mlx.semantics.domains import contract_digest
        forged_binding = deepcopy(self.handoff.bindings[0])
        object.__setattr__(forged_binding, "candidate_abi_index", 227)
        object.__setattr__(forged_binding, "candidate_type_ids", ("ForgedType",))
        object.__setattr__(forged_binding, "binding_digest", contract_digest(binding_projection(forged_binding)))
        forged = deepcopy(self.handoff)
        object.__setattr__(forged, "bindings", (forged_binding, *forged.bindings[1:]))
        object.__setattr__(forged, "digest", contract_digest(handoff_projection(forged)))
        with self.assertRaises(BilqisError):
            self.require(handoff=forged)
