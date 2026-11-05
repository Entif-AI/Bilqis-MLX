"""Real-source deterministic regeneration witness for the A12 authority audit."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bilqis_mlx.factory.skos_curriculum.checkers import compile_source_constructive_lessons
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2
from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)
from bilqis_mlx.semantics.atlas.vocabulary import VocabularyPrior, plan_vocabulary_extension
from bilqis_mlx.semantics.atlas.vocabulary_resources import build_registry_mirror_delta
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas_projection import compile_atlas_release, persist_atlas_release
from bilqis_mlx.semantics.atlas_release_audit import audit_atlas_authority
from bilqis_mlx.semantics.frame_codec import SchemaTagMap
from bilqis_mlx.semantics.released_frame_schemas import (
    _load_pinned_released_frame_schemas, seal_released_frame_schemas,
)


@unittest.skipUnless(
    os.environ.get("BILQIS_A01_ATLAS_BUNDLE")
    and os.environ.get("BILQIS_A01_SOURCE_BUNDLE"),
    "real pinned A01 artifact/source bundle is an optional integration witness",
)
class AtlasAuthorityRealReplayTests(unittest.TestCase):
    @staticmethod
    def _pin():
        root = Path(__file__).resolve().parents[3]
        registry = json.loads(
            (root / "bilqis_mlx/semantics/atlas_source_pins_v1.json").read_text())
        return root, registry["entries"][0]

    def _regenerate_once(self, artifact_root: Path):
        root, pin = self._pin()
        source_bundle_path = Path(os.environ["BILQIS_A01_SOURCE_BUNDLE"])
        prior_abi_path = root / "bilqis_mlx/semantics/copular_registry_v1.json"

        accepted = load_pinned_atlas_snapshot(AtlasArtifactSelection(
            os.environ.get("BILQIS_A01_ATLAS_BUNDLE", "synthetic:unused"),
            pin["bundle_id"], pin["release_sha256"], pin["source_bundle_id"]))
        release = compile_atlas_release(
            source_bundle_path,
            source_bundle_path / "coverage.json",
            prior_abi_path,
            accepted.formal_domain_bindings,
        )
        persisted = persist_atlas_release(release, artifact_root)
        self.assertEqual(release.digest, pin["release_sha256"])
        self.assertEqual(persisted.bundle_id, pin["bundle_id"])
        self.assertEqual(release.source_bundle_id, pin["source_bundle_id"])

        selection = AtlasArtifactSelection(
            persisted.path, persisted.bundle_id, release.digest,
            release.source_bundle_id)
        snapshot = load_pinned_atlas_snapshot(selection)
        lessons = compile_source_constructive_lessons(selection)
        lesson_ids = {lesson.semantic_id for lesson in lessons.lessons}

        candidate = next(
            entry for entry in snapshot.abi_entries
            if entry.source == "CANONICAL_SKOS" and not entry.active
            and entry.semantic_id in lesson_ids
            and any(item.concept.semantic_id == entry.semantic_id
                    for item in snapshot.concepts))

        feature_schema = FeatureSchema((), ())
        features = build_feature_manifest(snapshot, feature_schema)
        active = tuple(entry.semantic_id for entry in snapshot.abi_entries if entry.active)
        bank_count = max(
            1,
            max((entry.index for entry in snapshot.abi_entries if entry.active), default=0)
            // ModelTopologySpecV2.semantic_bank_rows + 1,
        )
        prior = VocabularyPrior(
            selection,
            GenerationExtents(
                bank_count, 1, snapshot.active_set_sha256, "b" * 64,
                features.digest),
            features, feature_schema, active, "e" * 64)
        abi = plan_vocabulary_extension(
            prior, (candidate.semantic_id,), ModelTopologySpecV2())
        mirror = build_registry_mirror_delta(
            prior, abi, source_bundle_path=source_bundle_path)

        ast = _load_pinned_released_frame_schemas("boolean", selection)
        schemas = tuple(body.parse() for body in ast.manifest.bodies)
        resealed = seal_released_frame_schemas(
            schemas, SchemaTagMap.from_schemas(snapshot.release_sha256, schemas),
            snapshot)
        self.assertEqual(resealed.digest, ast.trusted_sha256)

        receipt = audit_atlas_authority(
            selection, abi, ast, lessons, mirror,
            abi_prior=prior, source_bundle_path=source_bundle_path)
        allocation = abi.allocations[0]
        prior_map = {
            entry.semantic_id: entry.index for entry in snapshot.abi_entries
            if entry.source == "PRIOR_ACCEPTED_NATIVE_REGISTRY"
        }
        prior_active_indices = tuple(
            entry.index for entry in snapshot.abi_entries if entry.active)
        return {
            "selection": selection,
            "snapshot": snapshot,
            "lessons": lessons,
            "abi": abi,
            "receipt": receipt,
            "selected": candidate.semantic_id,
            "allocation": allocation,
            "prior_map": prior_map,
            "prior_active_indices": prior_active_indices,
        }

    def test_two_real_regenerations_are_identical_and_propagate_new_semantic(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = self._regenerate_once(root / "first")
            second = self._regenerate_once(root / "second")

        self.assertEqual(first["selection"].bundle_id, second["selection"].bundle_id)
        self.assertEqual(
            first["selection"].release_sha256, second["selection"].release_sha256)
        self.assertEqual(
            first["receipt"].consumer_bindings,
            second["receipt"].consumer_bindings)
        self.assertEqual(first["receipt"].audit_sha256, second["receipt"].audit_sha256)
        self.assertEqual(
            first["receipt"].graph_projection_sha256,
            second["receipt"].graph_projection_sha256)

        for result in (first, second):
            selected = result["selected"]
            allocation = result["allocation"]
            snapshot = result["snapshot"]
            self.assertTrue(any(
                lesson.semantic_id == selected for lesson in result["lessons"].lessons))
            self.assertEqual(snapshot.abi_for_semantic(selected).index, allocation.abi_index)
            self.assertEqual(snapshot.concept(selected).abi_index, allocation.abi_index)
            self.assertEqual(
                result["abi"].active_indices,
                tuple(sorted((*result["prior_active_indices"], allocation.abi_index))))

        self.assertEqual(first["selected"], second["selected"])
        self.assertEqual(first["prior_map"], second["prior_map"])


if __name__ == "__main__":
    unittest.main()
