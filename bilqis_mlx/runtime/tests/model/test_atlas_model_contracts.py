"""B11 model-contract custody regressions that require no pinned A01 bundle."""
from pathlib import Path
import unittest

from bilqis_mlx.learning.source_atoms import SourceAtomRow
from bilqis_mlx.learning.tests.test_frame_encoder import FrameEncoderTests
from bilqis_mlx.runtime.atlas_model import BamfCompiledBatch
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_features import FeatureSchema


class BamfCompiledBatchOwnerTests(unittest.TestCase):
    def test_revalidation_preserves_existing_atlas_feature_owner(self):
        fixture = FrameEncoderTests()
        fixture.setUp()
        compiled, _vectors, _ast = fixture.compiled_inputs()
        source = SourceAtomRow(
            AtlasArtifactSelection(
                "/fixture", "1" * 64, compiled.features.semantic_release,
                "2" * 64),
            {"id": "fixture:model-contract"}, {}, Path("."), 1, 1)
        batch = BamfCompiledBatch(
            compiled, (source,), FeatureSchema((), ()))
        owner = batch.atlas_feature_artifact_owner

        batch.__post_init__()

        self.assertIs(batch.atlas_feature_artifact_owner, owner)
        self.assertEqual(
            owner.require(compiled.features), owner.current_node)


if __name__ == "__main__":
    unittest.main()
