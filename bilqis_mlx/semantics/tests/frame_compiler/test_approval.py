"""Frame compiler: approval contracts."""
from __future__ import annotations
from dataclasses import replace
from unittest import TestCase
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_compiler import compile_prefix, reconstruct
from bilqis_mlx.semantics.tests.frame_compiler.fixtures import (
    RELEASE, _case,
)


class ApprovalTests(TestCase):
    def test_first_admission_raw_atom_requires_source_owned_grant(self):
        ast, config = _case()
        first = ast.atoms[0]
        no_frame = replace(config, approved=None)
        ungranted = replace(
            no_frame, frontier=replace(
                no_frame.frontier, grants=tuple(
                    grant for grant in no_frame.frontier.grants
                    if grant.source_handle != first.source_reference)))
        with self.assertRaises(BilqisError) as caught:
            compile_prefix(ast, 1, RELEASE, ungranted)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_ATOM_SOURCE_UNAUTHORIZED")
        revoked = replace(
            no_frame, frontier=replace(
                no_frame.frontier, grants=tuple(
                    replace(grant, revoked=True)
                    if grant.source_handle == first.source_reference else grant
                    for grant in no_frame.frontier.grants)))
        with self.assertRaises(BilqisError) as caught:
            compile_prefix(ast, 1, RELEASE, revoked)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_ATOM_SOURCE_UNAUTHORIZED")
        tampered = replace(
            ast, atoms=(replace(first, token="unattested"), *ast.atoms[1:]))
        with self.assertRaises(BilqisError) as caught:
            compile_prefix(tampered, 1, RELEASE, no_frame)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_PREFIX_ATOM_SOURCE_UNAUTHORIZED")


    def test_atom_only_stream_needs_no_future_frame_approval(self):
        ast, config = _case()
        atoms_only = replace(ast, frames=())
        no_frames = replace(config, approved=None)
        for prefix in range(9):
            compiled = compile_prefix(
                atoms_only, prefix, RELEASE, no_frames)
            self.assertEqual(len(compiled.positions), prefix)
            self.assertIsNone(compiled.context_digest)
            self.assertEqual(
                reconstruct(compiled).atoms, ast.atoms[:prefix])
            self.assertEqual(reconstruct(compiled).frames, ())
            self.assertEqual(compiled.stats.actual_frames, 0)
            self.assertEqual(compiled.stats.sidecar_bytes, 0)


    def test_revoked_frame_grant_blocks_closure_not_raw_atom_prefix(self):
        ast, config = _case()
        revoked = replace(
            config.frontier,
            grants=tuple(
                replace(grant, revoked=True)
                if grant.source_handle == "source:frame:quad" else grant
                for grant in config.frontier.grants))
        blocked = replace(config, frontier=revoked)
        self.assertEqual(
            len(compile_prefix(ast, 7, RELEASE, blocked).positions), 7)
        with self.assertRaises(BilqisError):
            compile_prefix(ast, 8, RELEASE, blocked)
