"""Pre-admission B13 candidate feature replay boundaries."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.bamf_bundle import (
    issue_initial_foundation_feature_authority,
)
from bilqis_mlx.runtime.bamf_bundle import feature_authority
from bilqis_mlx.runtime.bamf_bundle.genesis import foundation as genesis_foundation
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    genesis_preparation, shape_patch,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.publication.publication_helpers import (
    host_source_authority_patch,
)
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_features import FeatureSchema

from .feature_authority_support import (
    ARBITRARY, ATLAS_BUNDLE, SOURCE_BUNDLE, frozen_snapshot, source_features,
)


class CandidateFeatureReplayTests(unittest.TestCase):
    def test_pre_admission_active_set_delta_preserves_source_feature_replay(self):
        features = source_features()
        selection = AtlasArtifactSelection(
            "/artifact", ATLAS_BUNDLE, features.semantic_release, SOURCE_BUNDLE)
        schema = FeatureSchema((), (), source_bindings=())
        foundation_replay = patch.multiple(
            genesis_foundation,
            _source_owned_feature_schema=lambda _selection: (
                frozen_snapshot(selection), schema),
            build_feature_manifest=lambda _snapshot, _schema: features,
        )
        with foundation_replay:
            authority = issue_initial_foundation_feature_authority(selection)
        with host_source_authority_patch(), foundation_replay:
            prepared = genesis_preparation(foundation_features=authority)
        candidate = replace(
            prepared.candidate,
            extents=replace(
                prepared.candidate.extents, active_semantic_digest=ARBITRARY),
            semantic_abi={
                **prepared.candidate.semantic_abi,
                "active_set_sha256": ARBITRARY,
            },
        )
        source_replay = patch.multiple(
            feature_authority,
            resolve_atlas_artifact_selection=lambda identity: AtlasArtifactSelection(
                "/artifact", identity.bundle_id, identity.release_sha256,
                identity.source_bundle_id),
            load_pinned_atlas_snapshot=frozen_snapshot,
            build_feature_manifest=lambda _snapshot, _schema: features,
        )
        with shape_patch(), source_replay:
            context = feature_authority.authenticate_bamf_candidate_feature_context(
                candidate, "/artifact")
        self.assertEqual(context.features.digest, features.digest)
        self.assertEqual(
            context.snapshot.active_set_sha256,
            prepared.candidate.extents.active_semantic_digest,
        )
        self.assertEqual(candidate.extents.active_semantic_digest, ARBITRARY)


if __name__ == "__main__":
    unittest.main()
