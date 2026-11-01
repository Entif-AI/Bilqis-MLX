"""B08.1 real A13-gated exact/structural reads and B01 gate arithmetic."""
from __future__ import annotations

from dataclasses import replace
import math
from unittest import TestCase

import numpy as np

from bilqis_mlx.learning.atlas_engram import (
    MotifManifest, MotifSlot, MotifFrameInput, motif_keys,
)
from bilqis_mlx.learning.atlas_engram_reads import schema_source_handle


RELEASE = "a" * 64

from .fixtures import RELEASE, _source, _parameters, _read

class NumericalReadTests(TestCase):
    def test_exact_hit_both_sites_use_literal_gate_and_keep_padding_unchanged(self):
        position, task, frontier, policy = _source()
        exact, structural = motif_keys(
            MotifFrameInput(position.envelope.frame, position.schema), RELEASE)
        manifest = MotifManifest(
            RELEASE, (MotifSlot(0, exact), MotifSlot(1, structural)))
        for site in (0, 1):
            _spec, _extents, _params, view = _parameters(site=site)
            before, result = _read(
                position, task, frontier, policy, manifest, view, site=site)
            self.assertEqual(result.dispositions, (("EXACT", "MISS"),))
            self.assertEqual(result.participating_slots, (0,))
            self.assertEqual(len(result.context_digests[0]), 64)
            expected = 2.0 / (1.0 + math.exp(4.0))
            self.assertAlmostEqual(float(result.hidden[0, 0, 0]), expected, places=6)
            np.testing.assert_array_equal(
                np.asarray(result.hidden[0, 1]), np.asarray(before[0, 1]))
            self.assertEqual(float(result.hidden[0, 0, 1]), 0.0)


    def test_structural_hit_then_missing_scope_and_foreign_release_are_safe(self):
        position, task, frontier, policy = _source()
        _exact, structural = motif_keys(
            MotifFrameInput(position.envelope.frame, position.schema), RELEASE)
        manifest = MotifManifest(RELEASE, (MotifSlot(0, structural),))
        _spec, _extents, _params, view = _parameters()
        _before, structural_result = _read(
            position, task, frontier, policy, manifest, view)
        self.assertEqual(structural_result.dispositions, (("STRUCTURAL", "MISS"),))
        self.assertEqual(structural_result.participating_slots, (0,))
        foreign_scope = replace(position, schema=replace(
            position.schema, scope="synthetic:other-story"))
        before, missed = _read(
            foreign_scope, task, frontier, policy, manifest, view)
        self.assertIs(missed.hidden, before)
        self.assertEqual(missed.dispositions, (("HELD", "MISS"),))
        before, foreign = _read(
            position, task, frontier, policy,
            MotifManifest("9" * 64), view)
        self.assertIs(foreign.hidden, before)
        self.assertEqual(foreign.dispositions, (("FOREIGN_RELEASE", "MISS"),))


    def test_revoked_frame_grant_and_missing_keys_return_exact_input_identity(self):
        position, task, frontier, policy = _source()
        exact, _structural = motif_keys(
            MotifFrameInput(position.envelope.frame, position.schema), RELEASE)
        manifest = MotifManifest(RELEASE, (MotifSlot(0, exact),))
        _spec, _extents, _params, view = _parameters()
        revoked = replace(frontier, grants=tuple(
            replace(grant, revoked=True)
            if grant.source_handle == position.envelope.source_handle else grant
            for grant in frontier.grants))
        before, held = _read(
            position, task, revoked, policy, manifest, view)
        self.assertIs(held.hidden, before)
        self.assertEqual(held.dispositions, (("HELD", "MISS"),))
        self.assertEqual(held.participating_slots, ())
        before, missed = _read(
            position, task, frontier, policy, MotifManifest(RELEASE), view)
        self.assertIs(missed.hidden, before)
        self.assertEqual(missed.dispositions, (("MISS", "MISS"),))


    def test_schema_grant_is_required_and_cannot_be_forged_or_revoked(self):
        position, task, frontier, policy = _source()
        exact, _structural = motif_keys(
            MotifFrameInput(position.envelope.frame, position.schema), RELEASE)
        manifest = MotifManifest(RELEASE, (MotifSlot(0, exact),))
        _spec, _extents, _params, view = _parameters()
        handle = schema_source_handle(position.schema)
        variants = (
            replace(frontier, grants=tuple(
                grant for grant in frontier.grants
                if grant.source_handle != handle)),
            replace(frontier, grants=tuple(
                replace(grant, revoked=True)
                if grant.source_handle == handle else grant
                for grant in frontier.grants)),
            replace(frontier, grants=tuple(
                replace(grant, evidence_digest="b"*64)
                if grant.source_handle == handle else grant
                for grant in frontier.grants)),
        )
        for altered in variants:
            before, result = _read(
                position, task, altered, policy, manifest, view)
            self.assertIs(result.hidden, before)
            self.assertEqual(result.dispositions, (("HELD", "MISS"),))
            self.assertEqual(result.participating_slots, ())
