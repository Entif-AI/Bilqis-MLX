"""B08.1 real A13-gated exact/structural reads and B01 gate arithmetic."""
from __future__ import annotations

from dataclasses import replace
import math
import os
from functools import lru_cache
from unittest import TestCase
import unittest

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
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.released_frame_schemas import (
    lookup_source_pinned_frame_schema,
)
from bilqis_mlx.semantics.frame_schema import (
    ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan,
    make_frame_instance,
)


RELEASE = "a" * 64
ACCESS_SCOPE = "synthetic:public"
FRAME_SCOPE = "synthetic:story"
REAL_RELEASE = "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306"
REAL_BUNDLE = "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7"
REAL_SOURCE_BUNDLE = "f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec"


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
