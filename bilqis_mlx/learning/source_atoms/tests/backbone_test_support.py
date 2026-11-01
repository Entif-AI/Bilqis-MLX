"""Shared real-source B11 producer test setup."""
from dataclasses import replace
from unittest import TestCase

from bilqis_mlx.learning.frame_embeddings import FeatureRequest
from bilqis_mlx.learning.source_atoms.backbone import (
    Group1MotifContext, start_source_backbone_numerical,
    start_source_backbone_producer,
)
from bilqis_mlx.learning.tests.motif_reads.fixtures import _source_bound_read_case
from bilqis_mlx.runtime.block_attnres import DepthFrameFeatures, depth_parameter_view
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.semantics.context_eligibility import (
    ContextMember, frame_evidence_digest, member_evidence_digest, project_context,
)
from bilqis_mlx.semantics.frame_schema import (
    ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan, make_frame_instance,
)
from bilqis_mlx.semantics.tests.test_context_eligibility import _case
from . import test_encoding as fixtures


class SourceBackboneTestBase(TestCase):
    setUp = fixtures.SourceEncodingTests.setUp

    def start(self, parameters=None, compiled=None, sources=None):
        return start_source_backbone_numerical(
            self.compiled if compiled is None else compiled,
            self.parameters if parameters is None else parameters,
            (self.source,) if sources is None else sources, self.schema)

    def motif_context(self):
        selection, _schema, _frame, _envelope, frontier, task, policy, position, manifest, _hidden = (
            _source_bound_read_case())
        return Group1MotifContext(
            ((position, None),), (task,), (frontier,), (policy,), manifest, selection)

    def producer(self, parameters=None, motif_context=None):
        return start_source_backbone_producer(
            self.compiled, self.parameters if parameters is None else parameters,
            (self.source,), self.schema,
            group1_motif=self.motif_context() if motif_context is None else motif_context)

    def depth_inputs(self, parameters, boundary=1):
        item = self.compiled.features.concepts[0]
        concept = ConceptRef(
            item.semantic_id, self.compiled.features.semantic_release,
            item.abi_index, item.type_ids, "source:test:none")
        envelopes, task, frontier, policy = _case(count=1, two_roles=True)
        schema = FrameSchema(
            "NONE", 1, "source:test:none",
            (RoleSpec("NONE", concept.type_ids, 1, 1),),
            "ORDERED", "source-expression")
        frame = make_frame_instance(
            schema, source_instance_id="fixture:b11-depth", structural_path=(),
            source_span=SourceSpan(0, 1), parent_occurrence_id=None,
            bindings=(RoleOccurrence("NONE", 0, concept=concept),), causal_prefix_end=1)
        member = ContextMember("NONE", 0, "source:member:none", 1)
        envelope = replace(envelopes[0], frame=frame, members=(member,),
                           semantic_release=self.compiled.features.semantic_release,
                           scope="source-expression")
        evidence = {
            envelope.source_handle: frame_evidence_digest(frame),
            member.source_handle: member_evidence_digest(frame, member),
        }
        grants = tuple(replace(
            frontier.grants[0], source_handle=handle, evidence_digest=digest,
            semantic_release=self.compiled.features.semantic_release,
        ) for handle, digest in sorted(evidence.items()))
        projection = project_context(
            (envelope,), replace(task, semantic_release=self.compiled.features.semantic_release,
                                 scope="source-expression", causal_prefix_end=1),
            replace(frontier, grants=grants), policy)
        request = FeatureRequest.from_context(projection, envelope.frame_handle, member.source_handle)
        features = DepthFrameFeatures((((request,), (request,)),), self.compiled.features, boundary)
        return features, depth_parameter_view(
            parameters, spec=ModelTopologySpecV2(), extents=self.compiled.extents,
            boundary_group=boundary)
