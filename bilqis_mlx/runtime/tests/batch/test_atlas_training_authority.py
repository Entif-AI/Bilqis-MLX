"""C02 rejects self-consistent but noncanonical A05/A06 inputs."""
from dataclasses import replace
import os
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_training_adapter import _require_semantic_authority
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection, load_pinned_atlas_snapshot
from bilqis_mlx.semantics.context_eligibility import ContextPolicy, SourceFrontier, TaskScope
from bilqis_mlx.semantics.frame_compiler import FrameCompilerConfig
from bilqis_mlx.semantics.released_frame_schemas import _load_pinned_released_frame_schemas

ARTIFACT = os.environ.get('BILQIS_ATLAS_REAL_ARTIFACT')

@unittest.skipUnless(ARTIFACT, 'real pinned A01 artifact not mounted')
class CanonicalTrainingAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selection = AtlasArtifactSelection(ARTIFACT,
            '5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7',
            '58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306',
            'f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec')
        snapshot = load_pinned_atlas_snapshot(cls.selection)
        cls.feature_schema = FeatureSchema((), ())
        cls.features = build_feature_manifest(snapshot, cls.feature_schema)
        pinned = _load_pinned_released_frame_schemas('micro', cls.selection).manifest
        cls.task = TaskScope('p', 't', 'TRAINING', snapshot.release_sha256, 'r', 's', 0, 0, 1)
        cls.frontier = SourceFrontier(1, 1, ())
        cls.policy = ContextPolicy('p', 1, 1, ('TRAINING',), ('PUBLIC_FORMAL',),
            ('r',), ('s',), ('PUBLIC_FORMAL',), (), ())
        cls.config = FrameCompilerConfig(tuple(body.parse() for body in pinned.bodies),
            pinned.schema_map, None, cls.task, cls.frontier, cls.policy)

    def check(self, config, features):
        _require_semantic_authority(config, features, None, self.task, self.frontier,
            self.policy, self.selection, self.feature_schema)

    def test_canonical_accepted_and_forged_graph_rejected(self):
        self.check(self.config, self.features)
        row = self.features.concepts[0]
        forged = replace(row, graph64=(9.0,) + row.graph64[1:])
        with self.assertRaises(BilqisError):
            self.check(self.config, replace(self.features, concepts=(forged,) + self.features.concepts[1:]))

    def test_same_schema_noncanonical_tag_map_rejected(self):
        entries = self.config.schema_map.entries
        swapped = tuple(sorted((replace(entries[0], tag=entries[1].tag),
                                replace(entries[1], tag=entries[0].tag), *entries[2:])))
        forged = replace(self.config.schema_map, entries=swapped)
        with self.assertRaises(BilqisError):
            self.check(replace(self.config, schema_map=forged), self.features)

    def test_unpinned_predecessor_and_missing_selection_fail_closed(self):
        with self.assertRaises(BilqisError):
            _require_semantic_authority(self.config, self.features, None, self.task, self.frontier,
                self.policy, None, self.feature_schema)
        with self.assertRaises(BilqisError):
            _require_semantic_authority(self.config, self.features, None, self.task, self.frontier,
                self.policy, self.selection, replace(self.feature_schema, predecessor=self.features))
