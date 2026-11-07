"""Post-cap migration proofs for B13.5 accepted feature authority."""
from dataclasses import replace
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.learning.atlas_acceptance import mint_acceptance_binding
from bilqis_mlx.runtime.bamf_bundle import (
    publish_bamf_generation, read_accepted_generation_feature_lineage,
    save_bamf_bundle,
)
from bilqis_mlx.runtime.bamf_bundle import feature_authority
from bilqis_mlx.runtime.bamf_bundle.records import BAMF_POINTER_SCHEMA, canonical
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.feature_authority_lineage_support import (
    FeatureLineageCase, SUCCESSOR_ATLAS_BUNDLE, SUCCESSOR_RELEASE,
    SUCCESSOR_SOURCE_BUNDLE, frozen_snapshot,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.test_feature_authority import (
    feature_bound, source_features,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, accepted_state, candidate, next_accepted_step, parent_state,
    retention_decision, shape_patch,
)
from bilqis_mlx.semantics.atlas.snapshot import load_atlas_snapshot
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas_projection import (
    compile_atlas_release, persist_atlas_release,
)
from bilqis_mlx.semantics.tests.atlas.projection.helpers import (
    PRIOR_ABI, _bindings, _fixture_bundle,
)


class AcceptedFeatureMigrationTests(FeatureLineageCase):
    def test_changed_release_replays_real_sibling_atlas_bundles(self):
        source_root = self.root / "source"
        source_root.mkdir()
        bundle, coverage, *_ = _fixture_bundle(source_root)
        atlas_root = self.root / "atlas"

        first_release = compile_atlas_release(
            bundle, coverage, PRIOR_ABI, _bindings())
        first_artifact = persist_atlas_release(first_release, atlas_root)
        first_snapshot = load_atlas_snapshot(first_artifact.path)
        first_features = build_feature_manifest(
            first_snapshot, FeatureSchema((), ()))

        second_release = compile_atlas_release(
            bundle, coverage, first_snapshot, _bindings())
        second_artifact = persist_atlas_release(second_release, atlas_root)
        second_snapshot = load_atlas_snapshot(second_artifact.path)
        second_features = build_feature_manifest(
            second_snapshot, FeatureSchema((), (), first_features))
        self.assertNotEqual(first_artifact.bundle_id, second_artifact.bundle_id)

        first = self.publish(feature_bound(
            candidate(parent_state()), first_features,
            release=first_release.digest,
            atlas_bundle=first_artifact.bundle_id,
            source_bundle=first_release.source_bundle_id))
        changed = feature_bound(
            candidate(accepted_state(parent_state()), 1, first["manifest_sha256"]),
            second_features, release=second_release.digest,
            atlas_bundle=second_artifact.bundle_id,
            source_bundle=second_release.source_bundle_id)
        changed = replace(changed, transition={
            **changed.transition, "kind": "PARAMETER_EXTENSION",
            "invalidate_derived_caches": True})
        self.publish(changed)

        with shape_patch(), patch(
                "bilqis_mlx.semantics.atlas.snapshot._require_registered_source_pin"):
            receipt, current, predecessor = read_accepted_generation_feature_lineage(
                self.pointer, second_artifact.path)

        self.assertEqual(receipt.feature_sha256, second_features.digest)
        self.assertEqual(receipt.predecessor_feature_sha256, first_features.digest)
        self.assertEqual((current, predecessor), (second_features, first_features))

    def test_live_v2_cutover_preserves_changed_feature_construction_history(self):
        root = source_features()
        genesis = feature_bound(candidate(parent_state()), root)
        legacy_stage = self.run / "legacy-genesis"
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            first_manifest = save_bamf_bundle(genesis, legacy_stage)
        bundle_root = self.run / "bamf-bundles"
        bundle_root.mkdir(parents=True)
        first_target = bundle_root / first_manifest["manifest_sha256"]
        legacy_stage.rename(first_target)
        first_acceptance = acceptance(genesis)

        changed = replace(
            root, semantic_release=SUCCESSOR_RELEASE,
            atlas_bundle_id=SUCCESSOR_ATLAS_BUNDLE,
            source_bundle_id=SUCCESSOR_SOURCE_BUNDLE,
            predecessor_digest=root.digest)
        generation_one = feature_bound(
            candidate(
                accepted_state(parent_state()), 1,
                first_manifest["manifest_sha256"]),
            changed, release=SUCCESSOR_RELEASE,
            atlas_bundle=SUCCESSOR_ATLAS_BUNDLE,
            source_bundle=SUCCESSOR_SOURCE_BUNDLE)
        generation_one = replace(generation_one, transition={
            **generation_one.transition, "kind": "PARAMETER_EXTENSION",
            "invalidate_derived_caches": True})
        second_stage = self.run / "legacy-generation-one"
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            second_manifest = save_bamf_bundle(generation_one, second_stage)
        second_target = bundle_root / second_manifest["manifest_sha256"]
        second_stage.rename(second_target)
        second_acceptance = mint_acceptance_binding(
            retention_decision(
                parent=genesis.retained_state,
                retained=generation_one.retained_state),
            generation_one.retained_state, run_id=generation_one.run_id,
            generation=generation_one.generation,
            feature_sha256=generation_one.extents.factor_map_digest)

        acceptance_root = self.run / "bamf-acceptance"
        acceptance_root.mkdir()
        for manifest, binding in (
                (first_manifest, first_acceptance),
                (second_manifest, second_acceptance)):
            (acceptance_root / f"{manifest['manifest_sha256']}.json").write_bytes(
                canonical(binding.to_record()))
        self.pointer.write_bytes(canonical({
            "schema": BAMF_POINTER_SCHEMA,
            "run_id": generation_one.run_id,
            "generation": generation_one.generation,
            "parent_manifest_sha256": generation_one.parent_manifest_sha256,
            "bundle": f"bamf-bundles/{second_manifest['manifest_sha256']}",
            "manifest_sha256": second_manifest["manifest_sha256"],
            "acceptance_sha256": second_acceptance.digest,
        }))

        retained = feature_bound(
            candidate(
                next_accepted_step(generation_one.retained_state), 2,
                second_manifest["manifest_sha256"]),
            changed, release=SUCCESSOR_RELEASE,
            atlas_bundle=SUCCESSOR_ATLAS_BUNDLE,
            source_bundle=SUCCESSOR_SOURCE_BUNDLE)
        retained_acceptance = mint_acceptance_binding(
            retention_decision(
                parent=generation_one.retained_state,
                retained=retained.retained_state),
            retained.retained_state, run_id=retained.run_id,
            generation=retained.generation,
            feature_sha256=retained.extents.factor_map_digest)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            publish_bamf_generation(
                self.run, retained, acceptance=retained_acceptance)

        def replay(snapshot, schema):
            return changed if schema.predecessor is not None else root

        with shape_patch(), patch.object(
                feature_authority, "load_pinned_atlas_snapshot",
                side_effect=frozen_snapshot), patch.object(
                feature_authority, "build_feature_manifest", side_effect=replay):
            receipt, current, predecessor = read_accepted_generation_feature_lineage(
                self.pointer, "/artifact")

        self.assertEqual(receipt.generation, 2)
        self.assertEqual(receipt.feature_sha256, changed.digest)
        self.assertEqual(receipt.predecessor_feature_sha256, changed.digest)
        self.assertEqual((current, predecessor), (changed, changed))
