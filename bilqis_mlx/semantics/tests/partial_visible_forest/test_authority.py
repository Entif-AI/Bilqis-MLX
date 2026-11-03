"""Partial forest authority witnesses."""
from __future__ import annotations
from dataclasses import replace
from unittest import TestCase
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics import frame_compiler
from bilqis_mlx.semantics.frame_compiler import compile_prefix
from bilqis_mlx.semantics.tests.frame_compiler.fixtures import RELEASE, _mixed_case


class AuthorityTests(TestCase):
    def test_partial_visible_forest_rechecks_hidden_parent_current_grants(self):
        ast, config = _mixed_case()
        compiled = compile_prefix(ast, 4, RELEASE, config)
        receipt = frame_compiler.validate_partial_visible_forest(
            compiled, ast, config)
        hidden_handles = (
            "source:frame:mixed:2",
            "source:member:mixed:2:0",
        )

        for handle in hidden_handles:
            with self.subTest(handle=handle, mode="missing"):
                missing = replace(
                    config,
                    frontier=replace(
                        config.frontier,
                        grants=tuple(
                            grant for grant in config.frontier.grants
                            if grant.source_handle != handle)))
                self.assertEqual(
                    compile_prefix(ast, 4, RELEASE, missing),
                    compiled)
                with self.assertRaises(BilqisError) as caught:
                    frame_compiler.validate_partial_visible_forest(
                        compiled, ast, missing,
                        expected_receipt=receipt)
                self.assertEqual(
                    caught.exception.context["reason"],
                    "BAMF_PREFIX_PARTIAL_SOURCE_AUTHORITY_INVALID")

            with self.subTest(handle=handle, mode="revoked"):
                revoked = replace(
                    config,
                    frontier=replace(
                        config.frontier,
                        grants=tuple(
                            replace(grant, revoked=True)
                            if grant.source_handle == handle else grant
                            for grant in config.frontier.grants)))
                self.assertEqual(
                    compile_prefix(ast, 4, RELEASE, revoked),
                    compiled)
                with self.assertRaises(BilqisError) as caught:
                    frame_compiler.validate_partial_visible_forest(
                        compiled, ast, revoked,
                        expected_receipt=receipt)
                self.assertEqual(
                    caught.exception.context["reason"],
                    "BAMF_PREFIX_PARTIAL_SOURCE_AUTHORITY_INVALID")

        grant_drift = (
            ("evidence", {"evidence_digest": "0" * 64}),
            ("release", {"semantic_release": "b" * 64}),
            ("rights", {"rights_epoch": 2}),
            ("correction", {"correction_generation": 2}),
            ("observed-time", {"observed_at": 4}),
            ("effective-time", {"effective_from": 6}),
        )
        for mode, fields in grant_drift:
            with self.subTest(handle=hidden_handles[0], mode=mode):
                drifted = replace(
                    config,
                    frontier=replace(
                        config.frontier,
                        grants=tuple(
                            replace(grant, **fields)
                            if grant.source_handle == hidden_handles[0]
                            else grant
                            for grant in config.frontier.grants)))
                self.assertEqual(
                    compile_prefix(ast, 4, RELEASE, drifted),
                    compiled)
                with self.assertRaises(BilqisError) as caught:
                    frame_compiler.validate_partial_visible_forest(
                        compiled, ast, drifted,
                        expected_receipt=receipt)
                self.assertEqual(
                    caught.exception.context["reason"],
                    "BAMF_PREFIX_PARTIAL_SOURCE_AUTHORITY_INVALID")
