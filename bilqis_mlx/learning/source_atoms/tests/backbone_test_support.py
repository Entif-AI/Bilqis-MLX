"""Shared real-source B11 producer test setup."""
from dataclasses import replace
from unittest import TestCase

import mlx.core as mx

from bilqis_mlx.learning.frame_embeddings import FeatureRequest
from bilqis_mlx.learning.source_atoms.backbone import (
    start_source_backbone_numerical, start_source_backbone_producer,
)
from bilqis_mlx.runtime.atlas_artifact_owner import AtlasFeatureArtifactOwner
from bilqis_mlx.runtime.block_attnres import DepthFrameFeatures, depth_parameter_view
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2, expected_bamf_shapes
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.learning.frame_embeddings.tests import test_public_formal_types as formal_fixtures
from bilqis_mlx.semantics.frame_adapters import public_formal_context
from bilqis_mlx.semantics.frame_schema import FrameInstance
from bilqis_mlx.semantics.tests.frame_adapters.helpers import SOURCE_ROOT
from . import test_encoding as fixtures


class SourceBackboneTestBase(TestCase):
    def setUp(self):
        fixtures.SourceEncodingTests.setUp(self)
        projection, adapter = self._depth_context()
        framed = tuple(item for item in projection.envelopes
                       if type(item.frame) is FrameInstance)
        schemas = tuple(sorted({item.frame.frame_schema_id for item in framed}))
        roles = tuple(sorted({binding.role_id for item in framed
                              for binding in item.frame.bindings}))
        self.schema = FeatureSchema(roles, schemas, source_bindings=tuple(
            (schema, adapter.descriptor.adapter_id) for schema in schemas))
        features = build_feature_manifest(self.snapshot, self.schema)
        extents = replace(self.compiled.extents, factor_map_digest=features.digest)
        self.compiled = replace(self.compiled, features=features, extents=extents)
        self.artifact_owner = AtlasFeatureArtifactOwner(features, self.schema)
        self.parameters = {
            item.name: (self.parameters[item.name]
                        if self.parameters[item.name].shape == item.shape
                        else mx.zeros(item.shape, dtype=mx.float32))
            for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)}
        envelope = next(item for item in framed if item.members)
        self._depth_members = tuple(FeatureRequest.from_context(
            projection, envelope.frame_handle, member.source_handle)
            for member in envelope.members)

    def start(self, parameters=None, compiled=None, sources=None):
        return start_source_backbone_numerical(
            self.compiled if compiled is None else compiled,
            self.parameters if parameters is None else parameters,
            (self.source,) if sources is None else sources, self.schema,
            self.artifact_owner)

    def producer(self, parameters=None):
        return start_source_backbone_producer(
            self.compiled, self.parameters if parameters is None else parameters,
            (self.source,), self.schema, self.artifact_owner)

    def _depth_context(self):
        formal_fixtures.PublicFormalTypeCompositionTests.setUpClass()
        formal = formal_fixtures.PublicFormalTypeCompositionTests()
        adapter, row, graph, seed, each, profile = formal._cases()[0]
        task, policy, frontier = formal._context(self.snapshot)
        projection, _ = public_formal_context(
            adapter, row, self.snapshot, source_root=SOURCE_ROOT, graph=graph,
            task_scope=task, source_frontier=frontier, policy=policy,
            source_seed=seed, source_each=each, source_profile_parameters=profile)
        return projection, adapter

    def depth_inputs(self, parameters, boundary=1):
        requests = self._depth_members
        features = DepthFrameFeatures(
            ((requests, requests),), self.compiled.features, boundary,
            atlas_selection=self.source.selection)
        return features, depth_parameter_view(
            parameters, spec=ModelTopologySpecV2(), extents=self.compiled.extents,
            boundary_group=boundary)
