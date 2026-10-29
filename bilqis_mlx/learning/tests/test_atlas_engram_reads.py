"""B08.1 real A13-gated exact/structural reads and B01 gate arithmetic."""
from __future__ import annotations

from dataclasses import replace
import math
from functools import lru_cache
from unittest import TestCase

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_engram import (
    MotifManifest, MotifSlot, MotifFrameInput, motif_keys,
)
from bilqis_mlx.learning.atlas_engram_parameters import motif_parameter_view
from bilqis_mlx.learning.atlas_engram_reads import (
    MotifReadPosition, _read_motif_unqualified_candidate as read_motif,
    read_motif as guarded_read_motif, schema_evidence_digest,
    schema_source_handle,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
)
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextEligibility, ContextMember, ContextPolicy,
    SourceFrontier, SourceGrant, TaskScope,
    frame_evidence_digest, member_evidence_digest,
)
from bilqis_mlx.semantics.frame_schema import (
    ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan,
    make_frame_instance,
)


RELEASE = "a" * 64
ACCESS_SCOPE = "synthetic:public"
FRAME_SCOPE = "synthetic:story"


def _source(*, actor="formal:alice", patient="formal:bob"):
    schema = FrameSchema(
        "frame:pair", 1, "source:pair",
        (RoleSpec("actor", ("Person",), 1, 1),
         RoleSpec("patient", ("Person",), 1, 1)),
        "ORDERED", FRAME_SCOPE,
    )
    frame = make_frame_instance(
        schema, source_instance_id="synthetic:stream",
        structural_path=(), source_span=SourceSpan(0, 2),
        parent_occurrence_id=None,
        bindings=(
            RoleOccurrence("actor", 0, concept=ConceptRef(
                actor, RELEASE, 0, ("Person",), "source:actor")),
            RoleOccurrence("patient", 0, concept=ConceptRef(
                patient, RELEASE, 1, ("Person",), "source:patient")),
        ), causal_prefix_end=2,
    )
    members = (
        ContextMember("actor", 0, "source:member:actor", 2),
        ContextMember("patient", 0, "source:member:patient", 2),
    )
    envelope = ContextEligibility(
        "frame:0", frame, "source:frame:0", members,
        "synthetic:student", "synthetic:tenant", "TRAINING",
        PUBLIC_FORMAL, RELEASE, "synthetic:region", ACCESS_SCOPE,
        PUBLIC_FORMAL, 1, 1, 1, 0, 0, None, 2,
    )
    evidence = {
        envelope.source_handle: frame_evidence_digest(frame),
        schema_source_handle(schema): schema_evidence_digest(schema),
        **{member.source_handle: member_evidence_digest(frame, member)
           for member in members},
    }
    frontier = SourceFrontier(1, 1, tuple(sorted(
        (SourceGrant(
            handle, envelope.principal_id, envelope.tenant_id,
            PUBLIC_FORMAL, RELEASE, digest, ("TRAINING",),
            ("synthetic:region",), (ACCESS_SCOPE,),
            rights_epoch=1, correction_generation=1,
            observed_at=0, effective_from=0)
         for handle, digest in evidence.items()),
        key=lambda grant: grant.source_handle)))
    task = TaskScope(
        envelope.principal_id, envelope.tenant_id, "TRAINING",
        RELEASE, "synthetic:region", ACCESS_SCOPE, 1, 1, 2,
    )
    policy = ContextPolicy(
        "synthetic:policy", 1, 1, ("TRAINING",),
        (PUBLIC_FORMAL,), ("synthetic:region",), (ACCESS_SCOPE,),
        (PUBLIC_FORMAL,), ((PUBLIC_FORMAL, PUBLIC_FORMAL),), ())
    return MotifReadPosition(envelope, schema), task, frontier, policy


@lru_cache(maxsize=1)
def _base_parameters():
    spec = ModelTopologySpecV2()
    extents = GenerationExtents(1, 1, RELEASE, "b" * 64, "c" * 64)
    parameters = {
        item.name: mx.zeros(item.shape, dtype=mx.float32)
        for item in expected_bamf_shapes(spec, extents)
    }
    return spec, extents, parameters


def _parameters(*, site=0, slot_value=2.0):
    spec, extents, base = _base_parameters()
    parameters = dict(base)
    page = mx.zeros((16384, 128), dtype=mx.float32)
    page[0, 0] = slot_value
    page[1, 0] = slot_value + 1
    parameters["motif.page.0"] = page
    for index in (0, 1):
        projection = mx.zeros((768, 128), dtype=mx.float32)
        projection[0, 0] = 1.0
        parameters[f"motif.site.{index}.projection"] = projection
        parameters[f"motif.site.{index}.norm"] = mx.ones((768,), dtype=mx.float32)
        parameters[f"motif.site.{index}.bias"] = mx.array([-4.0], dtype=mx.float32)
    return spec, extents, parameters, motif_parameter_view(
        parameters, spec=spec, extents=extents, site_index=site)


def _read(position, task, frontier, policy, manifest, view, *, site=0,
          hidden=None, features=None):
    if hidden is None:
        hidden = mx.zeros((1, 2, 768), dtype=mx.float32)
    if features is None:
        features = mx.ones((1, 2, 128), dtype=mx.float32)
    return hidden, read_motif(
        site_index=site, hidden=hidden, features=features,
        positions=((position, None),), tasks=(task,),
        frontiers=(frontier,), policies=(policy,),
        manifest=manifest, parameters=view,
    )


class MotifReadTests(TestCase):
    def test_public_read_entrypoint_fails_closed_until_source_owner_issuer_exists(self):
        with self.assertRaises(BilqisError):
            guarded_read_motif()

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

    def test_hit_gradients_reach_page_projection_and_gate_at_each_site(self):
        position, task, frontier, policy = _source()
        exact, _structural = motif_keys(
            MotifFrameInput(position.envelope.frame, position.schema), RELEASE)
        manifest = MotifManifest(RELEASE, (MotifSlot(0, exact),))
        for site in (0, 1):
            spec, extents, params, _view = _parameters(site=site)
            for name in (
                "motif.page.0",
                f"motif.site.{site}.projection",
                f"motif.site.{site}.bias",
            ):
                def loss(tensor):
                    changed = dict(params)
                    changed[name] = tensor
                    view = motif_parameter_view(
                        changed, spec=spec, extents=extents,
                        site_index=site)
                    return mx.sum(_read(
                        position, task, frontier, policy, manifest,
                        view, site=site)[1].hidden)
                gradient = mx.grad(loss)(params[name])
                self.assertTrue(bool(mx.all(mx.isfinite(gradient))))
                self.assertGreater(float(mx.sum(mx.abs(gradient))), 0)

    def test_nonzero_gate_inputs_train_norm_and_both_gate_vectors(self):
        position, task, frontier, policy = _source()
        exact, _structural = motif_keys(
            MotifFrameInput(position.envelope.frame, position.schema), RELEASE)
        manifest = MotifManifest(RELEASE, (MotifSlot(0, exact),))
        hidden = mx.zeros((1, 2, 768), dtype=mx.float32)
        hidden[0, 0, 0] = 1.0
        for site in (0, 1):
            spec, extents, params, _view = _parameters(site=site)
            params = dict(params)
            for suffix, width in (("gate_hidden", 768), ("gate_feature", 128)):
                vector = mx.zeros((width,), dtype=mx.float32)
                vector[0] = 0.2
                params[f"motif.site.{site}.{suffix}"] = vector
            for suffix in ("norm", "gate_hidden", "gate_feature"):
                name = f"motif.site.{site}.{suffix}"
                def loss(tensor):
                    changed = dict(params)
                    changed[name] = tensor
                    view = motif_parameter_view(
                        changed, spec=spec, extents=extents, site_index=site)
                    return mx.sum(_read(
                        position, task, frontier, policy, manifest, view,
                        site=site, hidden=hidden)[1].hidden)
                gradient = mx.grad(loss)(params[name])
                self.assertTrue(bool(mx.all(mx.isfinite(gradient))))
                self.assertGreater(float(mx.sum(mx.abs(gradient))), 0)

    def test_wrong_site_or_invalid_tensor_rejects_before_gather(self):
        position, task, frontier, policy = _source()
        _spec, _extents, _params, view = _parameters()
        with self.assertRaises(BilqisError):
            _read(position, task, frontier, policy, MotifManifest(RELEASE),
                  view, site=1)
        with self.assertRaises(BilqisError):
            read_motif(
                site_index=0,
                hidden=mx.zeros((1, 2, 768), dtype=mx.float32),
                features=mx.ones((1, 2, 127), dtype=mx.float32),
                positions=((position, None),), tasks=(task,),
                frontiers=(frontier,), policies=(policy,),
                manifest=MotifManifest(RELEASE), parameters=view)
