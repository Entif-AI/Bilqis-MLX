"""Optional real-source replay witness for the A12 authority audit."""
import os
import json
from pathlib import Path
import unittest

from bilqis_mlx.factory.skos_curriculum.checkers import compile_source_constructive_lessons
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2
from bilqis_mlx.semantics.atlas.snapshot import load_pinned_atlas_snapshot
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas.vocabulary import VocabularyPrior, plan_vocabulary_extension
from bilqis_mlx.semantics.atlas.vocabulary_resources import build_registry_mirror_delta
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas_release_audit import audit_atlas_authority
from bilqis_mlx.semantics.released_frame_schemas import _load_pinned_released_frame_schemas

ROOT = Path(__file__).resolve().parents[3]


def _registered_real_selection() -> AtlasArtifactSelection:
    registry = json.loads(
        (ROOT / "bilqis_mlx/semantics/atlas_source_pins_v1.json").read_text())
    entry, = registry["entries"]
    return AtlasArtifactSelection(
        os.environ["BILQIS_A01_ATLAS_BUNDLE"],
        entry["bundle_id"], entry["release_sha256"], entry["source_bundle_id"])


@unittest.skipUnless(
    os.environ.get("BILQIS_A01_ATLAS_BUNDLE") and os.environ.get("BILQIS_A01_SOURCE_BUNDLE"),
    "real pinned A01 artifact/source bundle is an optional integration witness",
)
class AtlasAuthorityRealReplayTests(unittest.TestCase):
    def test_real_pinned_producers_replay_one_authority(self):
        selection = _registered_real_selection()
        snapshot = load_pinned_atlas_snapshot(selection)
        feature_schema = FeatureSchema((), ())
        features = build_feature_manifest(snapshot, feature_schema)
        active = tuple(entry.semantic_id for entry in snapshot.abi_entries if entry.active)
        bank_count = max(
            1, max((entry.index for entry in snapshot.abi_entries if entry.active), default=0)
            // ModelTopologySpecV2.semantic_bank_rows + 1)
        prior = VocabularyPrior(
            selection,
            GenerationExtents(bank_count, 1, snapshot.active_set_sha256,
                              "b" * 64, features.digest),
            features, feature_schema, active, "e" * 64)
        active_set = set(active)
        next_source = next(
            entry for entry in snapshot.abi_entries
            if entry.semantic_id not in active_set
            and any(item.concept.semantic_id == entry.semantic_id for item in snapshot.concepts)
            and not any(row.semantic_id == entry.semantic_id
                        and row.source_disposition != "SOURCE_ELIGIBLE"
                        for row in snapshot.withheld_rows))
        abi = plan_vocabulary_extension(prior, (next_source.semantic_id,), ModelTopologySpecV2())
        source_bundle_path = Path(os.environ["BILQIS_A01_SOURCE_BUNDLE"])
        mirror = build_registry_mirror_delta(prior, abi, source_bundle_path=source_bundle_path)
        ast = _load_pinned_released_frame_schemas("boolean", selection)
        lessons = compile_source_constructive_lessons(selection)
        receipt = audit_atlas_authority(
            selection, abi, ast, lessons, mirror,
            abi_prior=prior, source_bundle_path=source_bundle_path)
        self.assertEqual(receipt.source_release_sha256, snapshot.release_sha256)
        self.assertEqual(len(receipt.consumer_bindings), 5)
        self.assertEqual(
            receipt.prior_abi_sha256,
            "30d18c7140d49c168488416e04644b934ea79492561c2b73f65e55be18ed4e8c")


if __name__ == "__main__":
    unittest.main()
