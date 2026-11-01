"""Partial visible forest: visibility contracts."""
from __future__ import annotations
from dataclasses import replace
from unittest import TestCase
from bilqis_mlx.semantics import frame_compiler
from bilqis_mlx.semantics.context_eligibility import ApprovedContextProjection, frame_evidence_digest, member_evidence_digest, project_context
from bilqis_mlx.semantics.frame_compiler import compile_prefix
from bilqis_mlx.semantics.frame_schema import ChildFrameRef, FrameTree, RoleOccurrence, make_frame_instance
from bilqis_mlx.semantics.tests.frame_compiler.fixtures import (
    RELEASE, _mixed_case,
)


class VisibilityTests(TestCase):
    def test_partial_visible_forest_excludes_future_and_preserves_full_identities(self):
        ast, config = _mixed_case()
        parent = ast.frames[0].root
        child = ast.frames[0].children[0].root
        before = (
            parent.occurrence_id, parent.content_digest,
            child.occurrence_id, child.content_digest)

        at_three = frame_compiler.validate_partial_visible_forest(
            compile_prefix(ast, 3, RELEASE, config), ast, config)
        self.assertEqual(at_three.visible_forest, ())
        self.assertEqual(at_three.hidden_parents, ())

        at_four = frame_compiler.validate_partial_visible_forest(
            compile_prefix(ast, 4, RELEASE, config), ast, config)
        self.assertEqual(
            tuple(tree.root.occurrence_id for tree in at_four.visible_forest),
            (child.occurrence_id,))
        self.assertFalse(any(
            tree.root.occurrence_id == parent.occurrence_id
            for tree in at_four.visible_forest))

        at_eight = frame_compiler.validate_partial_visible_forest(
            compile_prefix(ast, 8, RELEASE, config), ast, config)
        full_parent = next(
            tree for tree in at_eight.visible_forest
            if tree.root.occurrence_id == parent.occurrence_id)
        after = (
            full_parent.root.occurrence_id, full_parent.root.content_digest,
            full_parent.children[0].root.occurrence_id,
            full_parent.children[0].root.content_digest)
        self.assertEqual(after, before)
        self.assertEqual(at_eight.hidden_parents, ())


    def test_partial_visible_forest_ignores_hidden_parent_member_content(self):
        ast, config = _mixed_case()
        parent_tree, atomic_tree = ast.frames
        parent = parent_tree.root
        child = parent_tree.children[0].root
        parent_schema = next(
            schema for schema in config.schemas
            if schema.schema_id == parent.frame_schema_id)
        changed_reference = ChildFrameRef(
            child.occurrence_id,
            child.content_digest,
            ("Frame", "SyntheticFutureVariant"))
        changed_parent = make_frame_instance(
            parent_schema,
            source_instance_id=parent.source_instance_id,
            structural_path=parent.structural_path,
            source_span=parent.source_span,
            parent_occurrence_id=parent.parent_occurrence_id,
            bindings=(RoleOccurrence(
                "child", 0, child_frame=changed_reference),),
            causal_prefix_end=parent.causal_prefix_end)
        changed_ast = replace(
            ast, frames=(
                FrameTree(changed_parent, parent_tree.children),
                atomic_tree))

        parent_envelope = next(
            envelope for envelope in config.approved.envelopes
            if envelope.frame.occurrence_id == parent.occurrence_id)
        changed_envelope = replace(parent_envelope, frame=changed_parent)
        evidence = {
            changed_envelope.source_handle:
                frame_evidence_digest(changed_parent)}
        evidence.update({
            member.source_handle: member_evidence_digest(
                changed_parent, member)
            for member in changed_envelope.members})
        changed_frontier = replace(
            config.frontier,
            grants=tuple(
                replace(grant, evidence_digest=evidence[grant.source_handle])
                if grant.source_handle in evidence else grant
                for grant in config.frontier.grants))
        changed_envelopes = tuple(
            changed_envelope
            if envelope.frame.occurrence_id == parent.occurrence_id
            else envelope
            for envelope in config.approved.envelopes)
        changed_approved = project_context(
            changed_envelopes, config.task,
            changed_frontier, config.policy)
        self.assertIsInstance(
            changed_approved, ApprovedContextProjection)
        changed_config = replace(
            config, approved=changed_approved,
            frontier=changed_frontier)

        original_prefix = compile_prefix(ast, 4, RELEASE, config)
        changed_prefix = compile_prefix(
            changed_ast, 4, RELEASE, changed_config)
        self.assertEqual(changed_prefix, original_prefix)
        self.assertEqual(
            frame_compiler.validate_partial_visible_forest(
                original_prefix, ast, config),
            frame_compiler.validate_partial_visible_forest(
                changed_prefix, changed_ast, changed_config))
        self.assertNotEqual(
            changed_parent.content_digest, parent.content_digest)
