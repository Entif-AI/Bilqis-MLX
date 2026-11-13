from __future__ import annotations

from dataclasses import replace
import unittest

from lib.ithkuil.src.skos.source_owner.row_witness import source_row_byte_witness
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ApprovedContextProjection, ContextHold, ContextPolicy,
    SourceFrontier, TaskScope, project_context,
)
from bilqis_mlx.semantics.frame_adapters.source_rows import _source_row_context


RELEASE = "a" * 64
ROOT = "lib/ithkuil/_data/csv"


def _case():
    witness = source_row_byte_witness(ROOT, "source", "source_sections", "NI-WEB-CH01:1.0")
    context = _source_row_context(
        witness,
        semantic_release=RELEASE, a01_source_bundle_id="b" * 64,
        semantic_id="ithkuil:fixture/source-section",
        principal_id="fixture:person",
        tenant_id="fixture:tenant",
        purpose="TRAINING",
        jurisdiction="fixture:region",
        scope="fixture:scope",
        policy_epoch=1,
        rights_epoch=2,
        correction_generation=3,
        observed_at=4,
        effective_from=0,
        causal_prefix_end=witness.record_end_byte,
    )
    task = TaskScope(
        "fixture:person", "fixture:tenant", "TRAINING", RELEASE,
        "fixture:region", "fixture:scope", 5, 5, witness.record_end_byte,
    )
    policy = ContextPolicy(
        "fixture:policy", 1, 2,
        ("TRAINING",), (PUBLIC_FORMAL,), ("fixture:region",),
        ("fixture:scope",), (PUBLIC_FORMAL,), (), (),
    )
    return context, task, policy


class SourceRowContextTests(unittest.TestCase):
    def test_source_owner_row_projects_only_with_issued_frame_and_member_grants(self):
        context, task, policy = _case()
        projected = project_context(
            (context.envelope,), task, SourceFrontier(2, 3, context.grants), policy)
        self.assertIsInstance(projected, ApprovedContextProjection)
        self.assertEqual(len(projected.attention_handles), 1)
        self.assertEqual(projected.frame(context.envelope.frame_handle), context.envelope.frame)

    def test_revoking_only_member_grant_invalidates_same_source_row(self):
        context, task, policy = _case()
        member_handle = context.envelope.members[0].source_handle
        grants = tuple(
            replace(item, revoked=True) if item.source_handle == member_handle else item
            for item in context.grants
        )
        projected = project_context(
            (context.envelope,), task, SourceFrontier(2, 3, grants), policy)
        self.assertIsInstance(projected, ContextHold)
        self.assertIn(member_handle, projected.source_handles)

    def test_missing_frame_grant_never_degrades_to_member_only_authority(self):
        context, task, policy = _case()
        grants = tuple(
            item for item in context.grants
            if item.source_handle != context.envelope.source_handle
        )
        projected = project_context(
            (context.envelope,), task, SourceFrontier(2, 3, grants), policy)
        self.assertIsInstance(projected, ContextHold)


if __name__ == "__main__":
    unittest.main()
