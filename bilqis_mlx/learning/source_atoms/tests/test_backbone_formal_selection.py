"""Public-formal frame types cross the execution-owned B05 boundary."""
from dataclasses import replace
from unittest import skipUnless

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.frame_embeddings import FeatureRequest, motif_gate_features
from bilqis_mlx.learning.frame_embeddings.tests import test_public_formal_types as formal_fixtures
from bilqis_mlx.learning.source_atoms.backbone import start_source_backbone_producer
from bilqis_mlx.runtime.block_attnres import DepthFrameFeatures, depth_parameter_view, depth_select
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2, expected_bamf_shapes
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.frame_adapters import public_formal_context
from bilqis_mlx.semantics.frame_schema import FrameInstance
from bilqis_mlx.semantics.tests.frame_adapters.helpers import SOURCE_ROOT
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE
from .backbone_test_support import SourceBackboneTestBase


@skipUnless(REAL_BUNDLE, 'real pinned A01 artifact not mounted')
class BackboneFormalSelectionTests(SourceBackboneTestBase):
    def test_public_formal_selection_and_forgery_at_producer_boundary(self):
        formal_fixtures.PublicFormalTypeCompositionTests.setUpClass()
        formal = formal_fixtures.PublicFormalTypeCompositionTests()
        selection = self.source.selection
        snapshot = self.snapshot
        adapter, row, graph, seed, each, profile = formal._cases()[0]
        task, policy, frontier = formal._context(snapshot)
        projection, _ = public_formal_context(
            adapter, row, snapshot, source_root=SOURCE_ROOT, graph=graph,
            task_scope=task, source_frontier=frontier, policy=policy,
            source_seed=seed, source_each=each, source_profile_parameters=profile)
        framed = tuple(item for item in projection.envelopes if type(item.frame) is FrameInstance)
        schema_ids = tuple(sorted({item.frame.frame_schema_id for item in framed}))
        roles = tuple(sorted({binding.role_id for item in framed for binding in item.frame.bindings}))
        schema = FeatureSchema(roles, schema_ids, source_bindings=tuple(
            (schema_id, adapter.descriptor.adapter_id) for schema_id in schema_ids))
        features = build_feature_manifest(snapshot, schema)
        extents = replace(self.compiled.extents, factor_map_digest=features.digest)
        compiled = replace(self.compiled, features=features, extents=extents)
        params = {item.name: mx.zeros(item.shape, dtype=mx.float32)
                  for item in expected_bamf_shapes(ModelTopologySpecV2(), extents)}
        params['features.norm'] = mx.ones((768,), dtype=mx.float32)
        params['depth.norm'] = mx.ones((768,), dtype=mx.float32)
        requests = motif_gate_features(
            params, projection, framed[0].frame_handle, features,
            extents=extents, atlas_selection=selection).requests
        self.assertTrue(requests)
        self.assertTrue(all(type(request) is FeatureRequest for request in requests))
        self.assertTrue(all(next(item for item in features.concepts
                                 if item.semantic_id == request.concept.semantic_id).source_status
                            == "ADMITTED_FORMAL_ABI_UNTYPED" for request in requests))
        producer = start_source_backbone_producer(compiled, params, (self.source,), schema)
        producer.advance()
        frame = DepthFrameFeatures(((requests, requests),), features, 1, atlas_selection=selection)
        view = depth_parameter_view(params, spec=ModelTopologySpecV2(), extents=extents, boundary_group=1)
        self.assertTrue(bool(mx.all(mx.isfinite(depth_select(producer, frame, view)))))
        for bad in (None, replace(selection, bundle_id='0' * 64)):
            with self.subTest(selection=bad), self.assertRaises(BilqisError):
                depth_select(producer, replace(frame, atlas_selection=bad), view)
