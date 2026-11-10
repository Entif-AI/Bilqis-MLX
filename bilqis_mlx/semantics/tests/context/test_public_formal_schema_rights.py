"""Source-owned schema rights used by B08 motif reads."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.context_eligibility import (
    ApprovedContextProjection, SourceFrontier, project_context,
)
from bilqis_mlx.semantics.frame_adapters.public_formal_grants import (
    issue_source_schema_grants, schema_evidence_digest, schema_source_handle,
)
from bilqis_mlx.semantics.frame_adapters.common import MICRO_PREDICATE_ADAPTER
from bilqis_mlx.semantics.frame_schema import FrameSchema, RoleSpec
from bilqis_mlx.semantics.tests.test_context_eligibility import (
    RELEASE, _case,
)


class PublicFormalSchemaRightsTests(TestCase):
    def _case(self):
        frames, task, frontier, policy = _case(count=1)
        projection = project_context(frames, task, frontier, policy)
        self.assertIsInstance(projection, ApprovedContextProjection)
        schema = FrameSchema(
            "frame:synthetic", 1, "source:synthetic",
            (RoleSpec("subject", ("Entity",), 1, 1),),
            "ORDERED", "synthetic",
        )
        selection = AtlasArtifactSelection(
            "synthetic:atlas", "b" * 64, RELEASE, "c" * 64)
        return schema, selection, projection, task, frontier, policy

    def _issue(self, schema, selection, projection, task, frontier, policy):
        with patch(
            "bilqis_mlx.semantics.frame_adapters.public_formal_grants."
            "lookup_source_pinned_frame_schema",
            return_value=(schema, object()),
        ):
            return issue_source_schema_grants(
                projection, source_adapter_id=MICRO_PREDICATE_ADAPTER,
                atlas_selection=selection, task_scope=task,
                source_frontier=frontier, policy=policy)

    def test_source_owner_issues_and_preserves_revoked_schema_rights(self):
        schema, selection, projection, task, frontier, policy = self._case()
        issued = self._issue(
            schema, selection, projection, task, frontier, policy)
        handle = schema_source_handle(schema)
        grant = next(item for item in issued.grants
                     if item.source_handle == handle)
        self.assertEqual(grant.evidence_digest, schema_evidence_digest(schema))
        self.assertFalse(grant.revoked)
        self.assertEqual(
            self._issue(schema, selection, projection, task, issued, policy),
            issued)

        revoked = replace(issued, grants=tuple(
            replace(item, revoked=True) if item.source_handle == handle else item
            for item in issued.grants))
        preserved = self._issue(
            schema, selection, projection, task, revoked, policy)
        retained = next(item for item in preserved.grants
                        if item.source_handle == handle)
        self.assertTrue(retained.revoked)

    def test_caller_cannot_replace_source_owned_schema_evidence(self):
        schema, selection, projection, task, frontier, policy = self._case()
        issued = self._issue(
            schema, selection, projection, task, frontier, policy)
        handle = schema_source_handle(schema)
        forged = replace(issued, grants=tuple(
            replace(item, evidence_digest="f" * 64)
            if item.source_handle == handle else item
            for item in issued.grants))
        with self.assertRaises(BilqisError):
            self._issue(schema, selection, projection, task, forged, policy)
