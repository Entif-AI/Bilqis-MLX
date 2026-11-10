"""B11 retained execution consumes the source-qualified B08 read at g1."""
import os
import unittest

import mlx.core as mx

from bilqis_mlx.learning.atlas_engram_reads.source_owner import _B13_EXECUTION_SEAL
from bilqis_mlx.learning.source_atoms.backbone import (
    start_retained_source_backbone_producer, start_source_backbone_producer,
)
from bilqis_mlx.learning.source_atoms.backbone_receipts import HIT, NO_HIT
from bilqis_mlx.learning.source_atoms.backbone_receipts import (
    INPUT_MOTIF_POSITION, MOTIF_POSITION,
)
from bilqis_mlx.runtime.backbone_group_numerical import _content_digest
from bilqis_mlx.runtime.atlas_artifact_owner import AtlasFeatureArtifactOwner
from bilqis_mlx.learning.tests.motif_reads.test_source_owner import (
    SourceOwnedMotifReadTests,
)
from bilqis_mlx.runtime.block_attnres import depth_parameter_view


@unittest.skipUnless(
    os.environ.get("BILQIS_ATLAS_REAL_ARTIFACT"),
    "real repo-pinned A01 artifact supplied at source turn-in",
)
class RetainedBackboneMotifTests(unittest.TestCase):
    def test_g1_receipt_records_actual_retained_motif_participation(self):
        (compiled, parameters, source, feature_schema, manifest, _spec, _extents,
         _hidden, _slot_id) = SourceOwnedMotifReadTests()._fixture()
        owner = AtlasFeatureArtifactOwner(compiled.features, feature_schema)
        plain = start_source_backbone_producer(
            compiled, parameters, (source,), feature_schema, owner).advance()
        retained = start_retained_source_backbone_producer(
            compiled, parameters, (source,), feature_schema, manifest, owner,
            seal=_B13_EXECUTION_SEAL).advance()
        mx.eval(plain.hidden, retained.hidden)
        retained_producer = start_retained_source_backbone_producer(
            compiled, parameters, (source,), feature_schema, manifest, owner,
            seal=_B13_EXECUTION_SEAL)
        h0 = retained_producer.receipts[0]
        g1 = retained_producer.advance()
        self.assertEqual(h0.motif_disposition, HIT)
        self.assertEqual(h0.motif_read_position, INPUT_MOTIF_POSITION)
        self.assertEqual(g1.motif_read_position, MOTIF_POSITION)
        self.assertEqual(g1.input_digest, _content_digest(h0.hidden))
        self.assertEqual(plain.motif_disposition, NO_HIT)
        self.assertEqual(retained.motif_disposition, HIT)
        self.assertNotEqual(retained.motif_read_digest, plain.motif_read_digest)
        self.assertEqual(float(mx.abs(plain.hidden[:, :-1]).sum()), 0.0)
        self.assertEqual(float(mx.abs(retained.hidden[:, :-1]).sum()), 0.0)
        self.assertGreater(float(retained.hidden[0, -1, 0]), 1.0)

    def test_source_owned_depth_inputs_execute_all_three_groups(self):
        (compiled, parameters, source, feature_schema, manifest, spec, extents,
         _hidden, _slot_id) = SourceOwnedMotifReadTests()._fixture()
        owner = AtlasFeatureArtifactOwner(compiled.features, feature_schema)
        producer = start_retained_source_backbone_producer(
            compiled, parameters, (source,), feature_schema, manifest, owner,
            seal=_B13_EXECUTION_SEAL)
        first = producer.advance()
        second = producer.advance(depth_parameters=depth_parameter_view(
            parameters, spec=spec, extents=extents, boundary_group=1))
        third = producer.advance(depth_parameters=depth_parameter_view(
            parameters, spec=spec, extents=extents, boundary_group=2))
        mx.eval(first.hidden, second.hidden, third.hidden)
        self.assertEqual(tuple(item.source_id for item in producer.receipts),
                         ("h0", "g1", "g2", "g3"))
        self.assertTrue(bool(mx.all(mx.isfinite(third.hidden))))
