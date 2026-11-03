"""Frame compiler: visibility contracts."""
from __future__ import annotations
from dataclasses import replace
import socket
from unittest import TestCase
from unittest.mock import patch
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.context_eligibility import ApprovedContextProjection, frame_evidence_digest, member_evidence_digest, project_context
from bilqis_mlx.semantics.frame_codec import PackDisposition
from bilqis_mlx.semantics.frame_compiler import PositionKind, SourceAtom, compile_prefix, reconstruct
from bilqis_mlx.semantics.frame_schema import ChildFrameRef, ConceptRef, FrameTree, RoleOccurrence, SourceSpan, make_frame_instance, occurrence_id
from bilqis_mlx.semantics.tests.frame_compiler.fixtures import (
    RELEASE, _case, _mixed_case, _with_atom_grants,
)


class VisibilityTests(TestCase):
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


    def test_future_suffix_does_not_change_prior_prefix_or_cache_key(self):
        ast, config = _case()
        for prefix in range(8):
            changed = replace(
                ast, atoms=ast.atoms[:prefix] + tuple(
                    replace(atom, token=atom.token + ":changed")
                    for atom in ast.atoms[prefix:]))
            self.assertEqual(
                compile_prefix(ast, prefix, RELEASE, config),
                compile_prefix(changed, prefix, RELEASE, config))
        before = compile_prefix(ast, 7, RELEASE, config)
        after = compile_prefix(ast, 8, RELEASE, config)
        self.assertEqual(after.positions[:len(before.positions)],
                         before.positions)
        self.assertNotEqual(after.cache_key, before.cache_key)


    def test_future_frame_member_change_cannot_enter_prior_prefix(self):
        ast, config = _case()
        original = ast.frames[0].root
        changed_binding = replace(
            original.bindings[-1], concept=ConceptRef(
                "formal:entity.99", RELEASE, 99, ("Entity",),
                "source:entity:99"))
        changed_frame = make_frame_instance(
            config.schemas[0],
            source_instance_id=original.source_instance_id,
            structural_path=original.structural_path,
            source_span=original.source_span,
            parent_occurrence_id=original.parent_occurrence_id,
            bindings=(*original.bindings[:-1], changed_binding),
            causal_prefix_end=original.causal_prefix_end)
        envelope = replace(
            config.approved.envelopes[0], frame=changed_frame)
        evidence = {
            envelope.source_handle: frame_evidence_digest(changed_frame)}
        evidence.update({
            member.source_handle: member_evidence_digest(
                changed_frame, member)
            for member in envelope.members})
        frontier = replace(
            config.frontier,
            grants=tuple(
                replace(grant, evidence_digest=evidence[grant.source_handle])
                if grant.source_handle in evidence else grant
                for grant in config.frontier.grants))
        approved = project_context(
            (envelope,), config.task, frontier, config.policy)
        self.assertIsInstance(approved, ApprovedContextProjection)
        changed_config = replace(
            config, approved=approved, frontier=frontier)
        changed_ast = replace(ast, frames=(FrameTree(changed_frame),))
        self.assertEqual(
            compile_prefix(ast, 7, RELEASE, config),
            compile_prefix(changed_ast, 7, RELEASE, changed_config))
        self.assertNotEqual(
            compile_prefix(ast, 8, RELEASE, config).cache_key,
            compile_prefix(
                changed_ast, 8, RELEASE, changed_config).cache_key)


    def test_invalid_future_frame_does_not_poison_earlier_prefix(self):
        ast, config = _case()
        malformed_future = FrameTree(
            ast.frames[0].root, (FrameTree(ast.frames[0].root),))
        changed = replace(ast, frames=(malformed_future,))
        self.assertEqual(
            compile_prefix(changed, 7, RELEASE, config),
            compile_prefix(ast, 7, RELEASE, config))
        with self.assertRaises(BilqisError):
            compile_prefix(changed, 8, RELEASE, config)


    def test_parent_cannot_close_while_child_is_future(self):
        ast, config = _mixed_case()
        child_schema, parent_schema = config.schemas
        source_id = ast.source_instance_id
        original_child = ast.frames[0].children[0].root
        future_child = make_frame_instance(
            child_schema, source_instance_id=source_id,
            structural_path=(0,), source_span=SourceSpan(4, 8),
            parent_occurrence_id=occurrence_id(source_id, ()),
            bindings=original_child.bindings, causal_prefix_end=8)
        early_parent = make_frame_instance(
            parent_schema, source_instance_id=source_id,
            structural_path=(), source_span=SourceSpan(0, 4),
            parent_occurrence_id=None,
            bindings=(RoleOccurrence(
                "child", 0, child_frame=ChildFrameRef(
                    future_child.occurrence_id, future_child.content_digest)),),
            causal_prefix_end=4)
        altered = replace(
            ast, frames=(FrameTree(
                early_parent, (FrameTree(future_child),)),))
        with self.assertRaises(BilqisError) as caught:
            compile_prefix(
                altered, 4, RELEASE, replace(config, approved=None))
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_CHILD_FUTURE")


    def test_member_visible_later_moves_closure_without_rewriting_prefix(self):
        ast, config = _case()
        envelope = config.approved.envelopes[0]
        delayed = replace(envelope.members[-1], visible_at_prefix=9)
        delayed_envelope = replace(
            envelope, members=(*envelope.members[:-1], delayed))
        frontier = replace(
            config.frontier,
            grants=tuple(
                replace(
                    grant, evidence_digest=member_evidence_digest(
                        envelope.frame, delayed))
                if grant.source_handle == delayed.source_handle else grant
                for grant in config.frontier.grants))
        task = replace(config.task, causal_prefix_end=10)
        approved = project_context(
            (delayed_envelope,), task, frontier, config.policy)
        self.assertIsInstance(approved, ApprovedContextProjection)
        delayed_config = replace(
            config, approved=approved, task=task, frontier=frontier)
        extended = replace(
            ast, atoms=ast.atoms + (
                SourceAtom(8, "token8", "source:atom:8"),
                SourceAtom(9, "token9", "source:atom:9")))
        delayed_config = _with_atom_grants(extended, delayed_config)
        before = compile_prefix(extended, 8, RELEASE, delayed_config)
        closed = compile_prefix(extended, 9, RELEASE, delayed_config)
        after = compile_prefix(extended, 10, RELEASE, delayed_config)
        self.assertEqual(len(before.positions), 8)
        self.assertEqual(closed.positions[:8], before.positions)
        self.assertEqual(after.positions[:len(closed.positions)],
                         closed.positions)
        closure = next(
            position for position in closed.positions
            if position.kind is PositionKind.CLOSURE)
        self.assertEqual(closure.source_index, 8)
        self.assertEqual(len(reconstruct(closed).frames), 1)
