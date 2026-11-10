"""B08.1 real A13-gated exact/structural reads and B01 gate arithmetic."""
from __future__ import annotations

from dataclasses import replace
import math
from types import SimpleNamespace
from unittest import TestCase

import numpy as np

from bilqis_mlx.learning.atlas_engram import (
    MotifManifest, MotifSlot, MotifFrameInput, build_motif_input, motif_keys,
)
from bilqis_mlx.learning.atlas_engram_reads import (
    MotifReadPosition, schema_evidence_digest, schema_source_handle,
)
from bilqis_mlx.learning.atlas_engram_reads.numerical import (
    _lookup_slot, _read_motif_unqualified_candidate,
)
from bilqis_mlx.learning._engram.tests.motif_fixtures import source as motif_source
from bilqis_mlx.semantics.context_eligibility import SourceGrant
from bilqis_mlx.semantics.tests.test_frame_compiler import _mixed_case


RELEASE = "a" * 64

from bilqis_mlx.learning.tests.motif_reads.fixtures import (
    RELEASE, _source, _parameters, _read,
)

class NumericalReadTests(TestCase):
    def test_nested_relation_lookup_uses_child_structure_from_read_row(self):
        nested_source = motif_source(child=True)
        child_source = nested_source.children[0]
        exact, _structural = motif_keys(nested_source, RELEASE)
        manifest = MotifManifest(RELEASE, (MotifSlot(0, exact),))
        parent_item = SimpleNamespace(
            envelope=SimpleNamespace(frame=nested_source.frame),
            schema=nested_source.schema,
        )
        child_item = SimpleNamespace(
            envelope=SimpleNamespace(frame=child_source.frame),
            schema=child_source.schema,
        )
        self.assertEqual(
            _lookup_slot(parent_item, manifest, (parent_item, child_item)),
            (0, "EXACT"),
        )

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

    def test_schema_rights_state_changes_read_identity_and_cannot_structural_borrow(self):
        position, task, frontier, policy = _source()
        _exact, structural = motif_keys(
            MotifFrameInput(position.envelope.frame, position.schema), RELEASE)
        manifest = MotifManifest(RELEASE, (MotifSlot(0, structural),))
        _spec, _extents, _params, view = _parameters()
        _before, live = _read(
            position, task, frontier, policy, manifest, view)
        handle = schema_source_handle(position.schema)
        self.assertEqual(live.dispositions, (("STRUCTURAL", "MISS"),))
        self.assertEqual(live.participating_slots, (0,))

        altered = (
            replace(frontier, grants=tuple(
                grant for grant in frontier.grants
                if grant.source_handle != handle)),
            replace(frontier, grants=tuple(
                replace(grant, revoked=True)
                if grant.source_handle == handle else grant
                for grant in frontier.grants)),
            replace(frontier, grants=tuple(
                replace(grant, evidence_digest="b" * 64)
                if grant.source_handle == handle else grant
                for grant in frontier.grants)),
        )
        identities = []
        for rights in altered:
            before, held = _read(
                position, task, rights, policy, manifest, view)
            self.assertIs(held.hidden, before)
            self.assertEqual(held.dispositions, (("HELD", "MISS"),))
            self.assertEqual(held.participating_slots, ())
            self.assertNotEqual(live.context_digests, held.context_digests)
            identities.append(held.context_digests)
        self.assertEqual(len(set(identities)), len(identities))

    def test_revoked_nested_child_cannot_feed_parent_lookup_or_gather(self):
        ast, config = _mixed_case()
        parent = ast.frames[0].root
        child = ast.frames[0].children[0].root
        envelopes = {item.frame.occurrence_id: item for item in config.approved.envelopes}
        schemas = {schema.schema_id: schema for schema in config.schemas}
        parent_position = MotifReadPosition(
            envelopes[parent.occurrence_id], schemas[parent.frame_schema_id])
        child_position = MotifReadPosition(
            envelopes[child.occurrence_id], schemas[child.frame_schema_id])
        row = (parent_position, child_position)
        qualified = {
            position.envelope.frame.occurrence_id:
                (position.envelope.frame, position.schema)
            for position in row
        }
        source = build_motif_input(parent.occurrence_id, qualified, {})
        exact, structural = motif_keys(source, RELEASE)
        base_grant = config.frontier.grants[0]
        schema_grants = tuple(
            SourceGrant(
                schema_source_handle(position.schema),
                config.task.principal_id, config.task.tenant_id,
                position.envelope.source_regime, RELEASE,
                schema_evidence_digest(position.schema),
                (config.task.purpose,), (config.task.jurisdiction,),
                (config.task.scope,), config.frontier.rights_epoch,
                config.frontier.correction_generation,
                observed_at=base_grant.observed_at,
                effective_from=base_grant.effective_from,
                effective_until=base_grant.effective_until,
            )
            for position in row
        )
        live_frontier = replace(
            config.frontier,
            grants=tuple(sorted(
                (*config.frontier.grants, *schema_grants),
                key=lambda grant: grant.source_handle)))
        child_handle = schema_source_handle(child_position.schema)
        revoked_frontier = replace(
            live_frontier,
            grants=tuple(
                replace(grant, revoked=True)
                if grant.source_handle == child_handle else grant
                for grant in live_frontier.grants))
        import mlx.core as mx
        hidden = mx.zeros((1, 2, 768), dtype=mx.float32)
        features = mx.ones((1, 2, 128), dtype=mx.float32)
        for site_index in (0, 1):
            _spec, _extents, _params, view = _parameters(site=site_index)
            for expected, key in (("EXACT", exact), ("STRUCTURAL", structural)):
                with self.subTest(site=site_index, key=expected):
                    manifest = MotifManifest(RELEASE, (MotifSlot(0, key),))
                    live = _read_motif_unqualified_candidate(
                        site_index=site_index, hidden=hidden, features=features,
                        positions=(row,), tasks=(config.task,),
                        frontiers=(live_frontier,), policies=(config.policy,),
                        manifest=manifest, parameters=view)
                    held = _read_motif_unqualified_candidate(
                        site_index=site_index, hidden=hidden, features=features,
                        positions=(row,), tasks=(config.task,),
                        frontiers=(revoked_frontier,), policies=(config.policy,),
                        manifest=manifest, parameters=view)
                    self.assertEqual(live.dispositions, ((expected, "MISS"),))
                    self.assertEqual(live.participating_slots, (0,))
                    np.testing.assert_array_equal(
                        np.asarray(held.hidden), np.asarray(hidden))
                    self.assertEqual(held.dispositions, (("HELD", "HELD"),))
                    self.assertEqual(held.participating_slots, ())
                    self.assertNotEqual(live.context_digests, held.context_digests)
