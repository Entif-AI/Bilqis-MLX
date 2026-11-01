"""Shared real-source B11 producer test setup."""
from unittest import TestCase

from bilqis_mlx.learning.frame_embeddings import FeatureRequest
from bilqis_mlx.learning.source_atoms.backbone import (
    start_source_backbone_numerical, start_source_backbone_producer,
)
from bilqis_mlx.runtime.block_attnres import DepthFrameFeatures, depth_parameter_view
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextEligibility, ContextMember, ContextPolicy,
    SourceFrontier, SourceGrant, TaskScope, frame_evidence_digest,
    member_evidence_digest, project_context,
)
from bilqis_mlx.semantics.frame_schema import (
    ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan,
    make_frame_instance,
)
from . import test_encoding as fixtures


class SourceBackboneTestBase(TestCase):
    setUp = fixtures.SourceEncodingTests.setUp

    def start(self, parameters=None, compiled=None, sources=None):
        return start_source_backbone_numerical(
            self.compiled if compiled is None else compiled,
            self.parameters if parameters is None else parameters,
            (self.source,) if sources is None else sources, self.schema)

    def producer(self, parameters=None):
        return start_source_backbone_producer(
            self.compiled, self.parameters if parameters is None else parameters,
            (self.source,), self.schema)

    def _depth_request(self):
        features = self.compiled.features
        concept = features.concepts[0]
        ref = ConceptRef(
            concept.semantic_id, features.semantic_release, concept.abi_index,
            concept.type_ids, "fixture:b11-depth")
        schema = FrameSchema(
            "UNKNOWN", 1, "source:b11-depth",
            (RoleSpec("UNKNOWN", ("Entity",), 1, 1),), "ORDERED", "fixture")
        frame = make_frame_instance(
            schema, source_instance_id="fixture:b11-depth", structural_path=(),
            source_span=SourceSpan(0, 1), parent_occurrence_id=None,
            bindings=(RoleOccurrence("UNKNOWN", 0, concept=ref),),
            causal_prefix_end=1)
        member = ContextMember("UNKNOWN", 0, "source:member:b11-depth", 1)
        envelope = ContextEligibility(
            "frame:b11-depth", frame, "source:frame:b11-depth", (member,),
            "fixture:principal", "fixture:tenant", "TRAINING", PUBLIC_FORMAL,
            features.semantic_release, "fixture:region", "fixture:scope",
            PUBLIC_FORMAL, 1, 1, 1, 0, 0, None, 1)
        evidence = {
            envelope.source_handle: frame_evidence_digest(frame),
            member.source_handle: member_evidence_digest(frame, member),
        }
        grants = tuple(SourceGrant(
            handle, "fixture:principal", "fixture:tenant", PUBLIC_FORMAL,
            features.semantic_release, digest, ("TRAINING",),
            ("fixture:region",), ("fixture:scope",), 1, 1, 0, 0)
            for handle, digest in evidence.items())
        task = TaskScope(
            "fixture:principal", "fixture:tenant", "TRAINING",
            features.semantic_release, "fixture:region", "fixture:scope", 0, 0, 1)
        policy = ContextPolicy(
            "fixture:policy", 1, 1, ("TRAINING",), (PUBLIC_FORMAL,),
            ("fixture:region",), ("fixture:scope",), (PUBLIC_FORMAL,),
            ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
            ((PUBLIC_FORMAL, PUBLIC_FORMAL, PUBLIC_FORMAL),))
        projection = project_context(
            (envelope,), task, SourceFrontier(1, 1, grants), policy)
        return FeatureRequest.from_context(
            projection, "frame:b11-depth", "source:member:b11-depth")

    def depth_inputs(self, parameters, boundary=1):
        request = self._depth_request()
        features = DepthFrameFeatures(
            (((request,), (request,)),), self.compiled.features, boundary)
        return features, depth_parameter_view(
            parameters, spec=ModelTopologySpecV2(), extents=self.compiled.extents,
            boundary_group=boundary)
