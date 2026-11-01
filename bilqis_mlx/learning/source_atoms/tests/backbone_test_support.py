"""Shared real-source B11 producer test setup."""
from dataclasses import replace
from unittest import TestCase

from bilqis_mlx.learning.source_atoms.backbone import (
    Group1MotifContext, start_source_backbone_numerical,
    start_source_backbone_producer,
)
from bilqis_mlx.learning.tests.motif_reads.fixtures import _source_bound_read_case
from bilqis_mlx.runtime.block_attnres import DepthFrameFeatures, depth_parameter_view
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.runtime.tests.depth.depth_helpers import _released_features
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
        released = _released_features(boundary)
        features = DepthFrameFeatures(
            ((released.requests[0][0], released.requests[0][1]),),
            released.features, boundary)
        extents = replace(
            self.compiled.extents, factor_map_digest=released.features.digest)
        return features, depth_parameter_view(
            parameters, spec=ModelTopologySpecV2(), extents=extents,
            boundary_group=boundary)
