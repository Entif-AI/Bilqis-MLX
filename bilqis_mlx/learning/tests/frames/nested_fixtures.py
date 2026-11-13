"""B02.4/B03.3: child-frame constituents have no invented semantic identity."""
from dataclasses import replace
import unittest
import mlx.core as mx
import numpy as np
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.frame_embeddings import (
    ChildFrameRequest, FeatureRequest, child_frame_source_context,
)
from bilqis_mlx.learning.frame_encoder import (
    AtomicFrameEmbedding, AtomicSourceHandle, CompiledEmbeddingVectors,
    CompiledEncoderInput, FrameEncoderInput, MemberEmbedding, encode_frames,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
)
from bilqis_mlx.semantics.atlas_features import ConceptFeature
from bilqis_mlx.semantics.context_eligibility import (
    ApprovedContextProjection, ContextMember, SourceFrontier,
    frame_evidence_digest, member_evidence_digest, project_context,
)
from bilqis_mlx.semantics.frame_compiler import (
    PositionKind, compile_prefix_rows, validate_partial_visible_forest,
)
from bilqis_mlx.semantics.frame_schema import (
    ChildFrameRef, FrameSchema, FrameTree, RoleOccurrence, RoleSpec,
    SourceSpan, make_frame_instance,
)
from bilqis_mlx.semantics.tests.test_atlas_features import _features
from bilqis_mlx.semantics.tests.test_frame_compiler import _mixed_case, RELEASE


def _source_features():
    # Synthetic A06 factor rows for the source-owned nested A05 test fixture.
    base = _features()
    return replace(
        base,
        concepts=(ConceptFeature(
            "formal:entity.1", 1, ("Entity",), (0.0,) * 64,
            "ADMITTED_SOURCE"),),
        type_map=(("Entity", 2), ("Frame", 3), ("NONE", 1), ("UNKNOWN", 0)),
        role_map=(("NONE", 1), ("UNKNOWN", 0), ("child", 3), ("subject", 2)),
        schema_map=(("NONE", 1), ("UNKNOWN", 0),
                    ("frame:child", 2), ("frame:parent", 3)),
    )


def _case():
    ast, config = _mixed_case()
    features = _source_features()
    extents = GenerationExtents(
        1, 1, "a" * 64, "b" * 64, features.digest)
    rng = np.random.default_rng(577)
    params = {
        item.name: mx.array(rng.normal(0, 0.02, item.shape).astype(np.float32))
        for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)
        if item.name.startswith(("frame.", "features."))
    }
    for name in ("frame.norm", "frame.interact_norm", "features.norm"):
        params[name] = mx.ones_like(params[name])
    rows = compile_prefix_rows(
        ((ast, 4, config), (ast, 8, config)), RELEASE)
    receipts = tuple(validate_partial_visible_forest(
        row, ast, config) for row in rows.rows)
    compiled = CompiledEncoderInput(
        rows, (config, config), features, extents,
        source_asts=(ast, ast), partial_forest_receipts=receipts)
    members = tuple(
        (MemberEmbedding(
            compiled.member_requests[index][0],
            mx.arange(768, dtype=mx.float32) / 1000),)
        for index in range(2))
    atomic = AtomicFrameEmbedding(
        AtomicSourceHandle(
            config.approved, "frame:mixed:1",
            "source:member:mixed:1:0"),
        mx.ones((768,), dtype=mx.float32))
    vectors = CompiledEmbeddingVectors(
        (mx.arange(4 * 768, dtype=mx.float32).reshape(4, 768) / 2000,
         mx.arange(8 * 768, dtype=mx.float32).reshape(8, 768) / 2000),
        members, ((), (atomic,)))
    return ast, config, compiled, vectors, params


def _source_valid_child_slot_variants():
    ast, config = _mixed_case()
    child = ast.frames[0].children[0].root
    original_parent = ast.frames[0].root
    schema = FrameSchema(
        "frame:parent-slot", 1, "source:parent",
        (RoleSpec("prefix", ("Entity",), 0, 1),
         RoleSpec("child", ("Frame",), 1, 1)),
        "ORDERED", "synthetic", ast_contract_sha256="b" * 64)
    child_ref = ChildFrameRef(
        child.occurrence_id, child.content_digest, ("Frame",))
    parent_variants = (
        (RoleOccurrence("child", 0, child_frame=child_ref),),
        (RoleOccurrence(
            "prefix", 0, concept=child.bindings[0].concept),
         RoleOccurrence("child", 0, child_frame=child_ref)),
    )
    child_envelope = next(
        item for item in config.approved.envelopes
        if item.frame.occurrence_id == child.occurrence_id)
    parent_template = next(
        item for item in config.approved.envelopes
        if item.frame.occurrence_id == original_parent.occurrence_id)
    grant_template = config.frontier.grants[0]
    requests = []
    for bindings in parent_variants:
        parent = make_frame_instance(
            schema, source_instance_id=original_parent.source_instance_id,
            structural_path=original_parent.structural_path,
            source_span=original_parent.source_span,
            parent_occurrence_id=None, bindings=bindings,
            causal_prefix_end=original_parent.causal_prefix_end)
        members = tuple(
            ContextMember(
                binding.role_id, binding.occurrence_index,
                "source:member:slot:" + binding.role_id,
                visible_at_prefix=8)
            for binding in parent.bindings)
        parent_envelope = replace(
            parent_template, frame_handle="frame:slot:parent",
            source_handle="source:frame:slot:parent",
            frame=parent, members=members)
        envelopes = (child_envelope, parent_envelope)
        grants = []
        for envelope in envelopes:
            grants.append(replace(
                grant_template, source_handle=envelope.source_handle,
                evidence_digest=frame_evidence_digest(envelope.frame)))
            for member in envelope.members:
                grants.append(replace(
                    grant_template, source_handle=member.source_handle,
                    evidence_digest=member_evidence_digest(
                        envelope.frame, member)))
        frontier = SourceFrontier(
            config.frontier.rights_epoch,
            config.frontier.correction_generation,
            tuple(sorted(grants, key=lambda grant: grant.source_handle)))
        projection = project_context(
            envelopes, config.task, frontier, config.policy)
        requests.append(ChildFrameRequest.from_context(
            projection, parent_envelope.frame_handle,
            "source:member:slot:child"))
    features = replace(
        _source_features(),
        schema_map=(("NONE", 1), ("UNKNOWN", 0),
                    ("frame:child", 2), ("frame:parent", 3),
                    ("frame:parent-slot", 4)))
    extents = GenerationExtents(
        1, 1, "a" * 64, "b" * 64, features.digest)
    rng = np.random.default_rng(578)
    params = {
        item.name: mx.array(
            rng.normal(0, 0.02, item.shape).astype(np.float32))
        for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)
        if item.name.startswith(("frame.", "features."))
    }
    return requests, features, extents, params
