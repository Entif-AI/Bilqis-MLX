"""B08.1 real A13-gated exact/structural reads and B01 gate arithmetic."""
from __future__ import annotations

from dataclasses import replace
import os
from unittest import TestCase
import unittest

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_engram import (
    MotifManifest, MotifSlot, MotifFrameInput, motif_keys,
)
from bilqis_mlx.learning.atlas_engram_reads import MotifReadPosition, read_motif as guarded_read_motif
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextEligibility, ContextMember, ContextPolicy,
    SourceFrontier, SourceGrant, TaskScope,
    frame_evidence_digest, member_evidence_digest,
)
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.released_frame_schemas import (
    lookup_source_pinned_frame_schema,
)
from bilqis_mlx.semantics.frame_schema import ConceptRef, RoleOccurrence, SourceSpan, make_frame_instance


RELEASE = "a" * 64

from .fixtures import ACCESS_SCOPE, REAL_RELEASE, REAL_BUNDLE, REAL_SOURCE_BUNDLE

from .fixtures import _source_bound_read_case

class GuardedReadTests(TestCase):
    def test_public_read_entrypoint_requires_source_qualified_contract(self):
        with self.assertRaises(TypeError):
            guarded_read_motif()


    @unittest.skipUnless(
        os.environ.get("BILQIS_ATLAS_REAL_ARTIFACT"),
        "real repo-pinned A01 artifact supplied at source turn-in",
    )
    def test_group1_second_read_is_source_qualified_but_quarantined_no_hit(self):
        (selection, schema, frame, envelope, frontier, task, policy,
         position, manifest, hidden) = _source_bound_read_case()

        result = guarded_read_motif(
            site_index=1, hidden=hidden,
            positions=((position, None),), tasks=(task,),
            frontiers=(frontier,), policies=(policy,), manifest=manifest,
            atlas_selection=selection,
            retained_generation_digest="d" * 64,
            parameter_tree_digest="e" * 64,
        )
        self.assertIs(result.hidden, hidden)
        self.assertEqual(
            result.dispositions, (("QUARANTINED_NO_HIT", "MISS"),))
        self.assertEqual(result.participating_slots, ())
        self.assertEqual(len(result.context_digests[0]), 64)

        forged = replace(position, schema=replace(schema, scope="forged"))
        with self.assertRaises(BilqisError):
            guarded_read_motif(
                site_index=1, hidden=hidden,
                positions=((forged, None),), tasks=(task,),
                frontiers=(frontier,), policies=(policy,), manifest=manifest,
                atlas_selection=selection,
                retained_generation_digest="d" * 64,
                parameter_tree_digest="e" * 64)

        for changed_frontier, changed_task in (
            (replace(frontier, rights_epoch=2), task),
            (replace(frontier, grants=tuple(
                replace(grant, revoked=True)
                if grant.source_handle == envelope.source_handle else grant
                for grant in frontier.grants)), task),
            (frontier, replace(task, causal_prefix_end=1)),
        ):
            held = guarded_read_motif(
                site_index=1, hidden=hidden,
                positions=((position, None),), tasks=(changed_task,),
                frontiers=(changed_frontier,), policies=(policy,),
                manifest=manifest, atlas_selection=selection,
                retained_generation_digest="d" * 64,
                parameter_tree_digest="e" * 64)
            self.assertIs(held.hidden, hidden)
            self.assertEqual(held.dispositions, (("HELD", "MISS"),))
            self.assertEqual(held.context_digests, (None,))

        guarded_read_motif(
            site_index=1, hidden=hidden,
            positions=((position, None),), tasks=(task,),
            frontiers=(frontier,), policies=(policy,), manifest=manifest,
            atlas_selection=selection,
            retained_generation_digest="d" * 64,
            parameter_tree_digest="e" * 64,
            expected_cache_digests=result.context_digests)
        with self.assertRaises(BilqisError):
            guarded_read_motif(
                site_index=1, hidden=hidden,
                positions=((position, None),), tasks=(task,),
                frontiers=(frontier,), policies=(policy,), manifest=manifest,
                atlas_selection=selection,
                retained_generation_digest="f" * 64,
                parameter_tree_digest="e" * 64,
                expected_cache_digests=result.context_digests)
