"""Source replay supplies the same complete context to allocation and reads."""
from dataclasses import replace
import inspect
import os
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_engram import motif_keys
from bilqis_mlx.learning.atlas_engram_reads import (
    schema_evidence_digest, schema_source_handle,
)
from bilqis_mlx.learning.atlas_engram_source import source_qualified_motif_context
from bilqis_mlx.semantics.context_eligibility import ContextHold, SourceFrontier
from bilqis_mlx.learning._engram.tests import test_atlas_engram_source as source_fixtures


@unittest.skipUnless(os.environ.get("BILQIS_ATLAS_REAL_ARTIFACT"),
                     "real repo-pinned A01 artifact required")
class MotifContextTests(unittest.TestCase):
    def replay(self, grade="A", **changes):
        source = source_fixtures.SourceQualifiedMotifTests()
        (selection, root, graph, adapter, row, task, policy,
         seed, each, profile) = source._case(grade)
        arguments = dict(
            source_root=root, graph=graph, task_scope=task,
            source_frontier=SourceFrontier(1, 1, ()), policy=policy,
            source_seed=seed, source_each=each,
            source_profile_parameters=profile)
        arguments.update(changes)
        return source_qualified_motif_context(adapter, row, selection, **arguments)

    def test_complete_source_frames_and_members_match_allocation_inputs(self):
        for grade in ("A", "B", "C"):
            with self.subTest(grade=grade):
                projection, inputs, frontier = self.replay(grade)
                planned, planned_frontier = source_fixtures.SourceQualifiedMotifTests()._prepare(grade=grade)
                self.assertEqual(projection.digest, planned.approved_context_digest)
                self.assertEqual(frontier, planned_frontier)
                self.assertTrue(inputs)
                for item in inputs:
                    envelope = next(envelope for envelope in projection.envelopes
                                    if envelope.frame.occurrence_id == item.frame.occurrence_id)
                    self.assertEqual(envelope.frame, item.frame)
                    self.assertEqual(tuple(member.key for member in envelope.members),
                                     tuple(binding.key for binding in item.frame.bindings))
                    for key in motif_keys(item, planned.candidate.proposed.manifest.semantic_release):
                        self.assertIsNotNone(planned.candidate.proposed.manifest.lookup(key))
                    grant = next(grant for grant in frontier.grants
                                 if grant.source_handle == schema_source_handle(item.schema))
                    self.assertEqual(grant.evidence_digest, schema_evidence_digest(item.schema))
                    self.assertFalse(grant.revoked)

    def test_source_prefix_hold_returns_no_qualified_context(self):
        task = source_fixtures.SourceQualifiedMotifTests()._case()[5]
        result = self.replay(task_scope=replace(task, causal_prefix_end=0))
        self.assertIsInstance(result, ContextHold)

    def test_revoked_member_is_not_reissued_or_replaced_with_a_structural_hit(self):
        _projection, _inputs, frontier = self.replay()
        revoked = replace(frontier, grants=tuple(
            replace(grant, revoked=True) if index == 0 else grant
            for index, grant in enumerate(frontier.grants)))
        with self.assertRaises(BilqisError):
            self.replay(source_frontier=revoked)

    def test_no_caller_projection_schema_or_allocation_authority(self):
        parameters = inspect.signature(source_qualified_motif_context).parameters
        for name in ("projection", "envelopes", "schemas", "manifest", "parent",
                     "parameters", "features", "source_family"):
            self.assertNotIn(name, parameters)

    def test_caller_cannot_replace_source_qualified_schema_grant(self):
        _projection, inputs, frontier = self.replay()
        handle = schema_source_handle(inputs[0].schema)
        canonical = next(grant for grant in frontier.grants
                         if grant.source_handle == handle)
        forged = replace(canonical, evidence_digest="0" * 64)
        with self.assertRaises(BilqisError):
            self.replay(source_frontier=SourceFrontier(
                frontier.rights_epoch, frontier.correction_generation, (forged,)))
