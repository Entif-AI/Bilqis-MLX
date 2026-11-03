"""Prefix compiler regressions."""
import unittest
from bilqis_mlx.semantics.tests.frame_compilation.helpers import (ApprovedContextProjection, AtomicFrame, BilqisError, ChildFrameRef, ConceptRef, FrameTree, PackDisposition, PositionKind, RELEASE, RoleOccurrence, SourceAtom, SourceSpan, _case, _mixed_case, _with_atom_grants, compile_prefix, frame_evidence_digest, make_frame_instance, member_evidence_digest, occurrence_id, project_context, reconstruct, replace)


class PrefixTests(unittest.TestCase):
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

    def test_nested_child_closes_before_parent_and_atomic_round_trips(self):
        ast, config = _mixed_case()
        self.assertEqual(
            compile_prefix(ast, 8, RELEASE, config),
            compile_prefix(
                replace(ast, frames=tuple(reversed(ast.frames))),
                8, RELEASE, config))
        at_four = reconstruct(compile_prefix(ast, 4, RELEASE, config))
        self.assertEqual(len(at_four.frames), 1)
        self.assertEqual(at_four.frames[0].root.frame_schema_id, "frame:child")
        at_six = reconstruct(compile_prefix(ast, 6, RELEASE, config))
        self.assertEqual(len(at_six.frames), 2)
        self.assertTrue(any(isinstance(tree.root, AtomicFrame)
                            for tree in at_six.frames))
        at_eight = compile_prefix(ast, 8, RELEASE, config)
        closures = tuple(
            position for position in at_eight.positions
            if position.kind is PositionKind.CLOSURE)
        self.assertEqual(len(closures), 3)
        self.assertEqual(tuple(
            position.packed.disposition for position in closures), (
                PackDisposition.EXTENDED,
                PackDisposition.ATOMIC,
                PackDisposition.EXTENDED))
        visible = reconstruct(at_eight)
        parent = next(
            tree for tree in visible.frames
            if getattr(tree.root, "frame_schema_id", None) == "frame:parent")
        self.assertEqual(len(parent.children), 1)
        self.assertEqual(
            parent.children[0].root.frame_schema_id, "frame:child")
        self.assertEqual(visible.atoms, ast.atoms)
        self.assertEqual(at_eight.stats.disposition_shares, (
            ("COMPACT", 0, 3), ("EXTENDED", 2, 3),
            ("ATOMIC", 1, 3)))
        self.assertGreater(at_eight.stats.sidecar_bytes, 0)

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
