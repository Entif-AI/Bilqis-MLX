"""Integration-bound A12 semantic-authority witnesses."""
from dataclasses import replace
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.skos_curriculum import compile_source_constructive_lessons
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2
from bilqis_mlx.semantics.atlas.snapshot import load_pinned_atlas_snapshot
from bilqis_mlx.semantics.atlas.vocabulary import VocabularyPrior, plan_vocabulary_extension
from bilqis_mlx.semantics.atlas.vocabulary_resources import build_registry_mirror_delta
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas_release_audit import audit_atlas_authority
from bilqis_mlx.semantics.released_frame_schemas import _load_pinned_released_frame_schemas

from bilqis_mlx.semantics.tests.test_atlas_release_audit import _selection


def _held_gloss_fixture():
    from bilqis_mlx.factory.tests.test_skos_curriculum import _snapshot
    from bilqis_mlx.semantics.atlas_projection import AtlasLabel

    original = _snapshot()
    held = next(
        row for row in original.withheld_rows
        if row.source_disposition == "SOURCE_HELD")
    admitted = original.concepts[0]
    renamed = replace(
        admitted,
        concept=replace(
            admitted.concept,
            labels=(
                AtlasLabel("altLabel", "near synonym"),
                AtlasLabel(
                    "prefLabel",
                    "plausible English gloss matching the held source"),
            )))
    return original, replace(
        original, concepts=(renamed, *original.concepts[1:])), held


class AtlasAuthorityIntegrationTests(unittest.TestCase):
    def _assert_held_source_stays_unadmitted(self, snapshot, held):
        from bilqis_mlx.factory.skos_curriculum import (
            LearnedFrontier, SOURCE_FAMILY_ADAPTERS,
            _compile_semantic_curriculum_snapshot,
            _compile_source_constructive_lessons_snapshot,
        )
        from bilqis_mlx.semantics.atlas_features import (
            plan_prospective_identity_features,
        )
        from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection

        admitted_ids = {entry.semantic_id for entry in snapshot.abi_entries}
        self.assertNotIn(held.semantic_id, admitted_ids)
        features = build_feature_manifest(snapshot, FeatureSchema((), ()))
        self.assertIn((held.semantic_id, held.reason_code), features.held_reasons)
        with self.assertRaises(BilqisError) as caught:
            features.features_for(
                held.semantic_id, "UNKNOWN", "UNKNOWN", "task:held")
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_FEATURE_CONCEPT_NOT_ADMITTED")
        with self.assertRaises(BilqisError):
            plan_prospective_identity_features(
                snapshot, features, (held.semantic_id,),
                expected_feature_digest=features.digest)

        selection = AtlasArtifactSelection(
            "fixture", snapshot.bundle_id, snapshot.release_sha256,
            snapshot.source_bundle_id)
        active = tuple(
            entry.semantic_id for entry in snapshot.abi_entries if entry.active)
        prior = VocabularyPrior(
            selection,
            GenerationExtents(
                1, 1, snapshot.active_set_sha256,
                "b" * 64, features.digest),
            features, FeatureSchema((), ()), active, "e" * 64)
        with patch(
                "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
                return_value=snapshot), self.assertRaises(BilqisError):
            plan_vocabulary_extension(
                prior, (held.semantic_id,), ModelTopologySpecV2())

        source_lessons = _compile_source_constructive_lessons_snapshot(
            snapshot).lessons
        self.assertFalse(any(
            held.semantic_id in (
                lesson.semantic_id, *lesson.constituents,
                *lesson.prerequisite_closure)
            for lesson in source_lessons))
        teacher = _compile_semantic_curriculum_snapshot(
            snapshot, SOURCE_FAMILY_ADAPTERS,
            LearnedFrontier(
                snapshot.release_sha256,
                claimed_exposed=(held.semantic_id,),
                claimed_qualified=(held.semantic_id,)))
        self.assertNotIn(held.semantic_id, teacher.source_eligible_concept_ids)
        self.assertFalse(any(
            held.semantic_id in (
                lesson.semantic_id, *lesson.constituents,
                *lesson.prerequisite_closure)
            for lesson in teacher.source_lessons))
        self.assertEqual(
            next(row for row in teacher.source_hold_rows
                 if row.semantic_id == held.semantic_id).reason_code,
            held.reason_code)

    def test_held_gloss_cannot_promote_across_semantic_or_teacher_surfaces(self):
        original, relabeled, held = _held_gloss_fixture()
        for snapshot in (original, relabeled):
            with self.subTest(labels=snapshot.concepts[0].concept.labels):
                self._assert_held_source_stays_unadmitted(snapshot, held)

    @unittest.skipUnless(
        os.environ.get("BILQIS_A01_ATLAS_BUNDLE")
        and os.environ.get("BILQIS_A01_SOURCE_BUNDLE"),
        "real pinned A01 artifact/source bundle is an optional integration witness",
    )
    def test_real_pinned_producers_replay_one_authority(self):
        selection = _selection()
        selection = replace(
            selection, path=os.environ["BILQIS_A01_ATLAS_BUNDLE"])
        snapshot = load_pinned_atlas_snapshot(selection)
        feature_schema = FeatureSchema((), ())
        features = build_feature_manifest(snapshot, feature_schema)
        active = tuple(
            entry.semantic_id for entry in snapshot.abi_entries if entry.active)
        bank_count = max(
            1,
            max((entry.index for entry in snapshot.abi_entries if entry.active),
                default=0) // ModelTopologySpecV2.semantic_bank_rows + 1)
        prior = VocabularyPrior(
            selection,
            GenerationExtents(
                bank_count, 1, snapshot.active_set_sha256,
                "b" * 64, features.digest),
            features, feature_schema, active, "e" * 64)
        active_set = set(active)
        next_source = next(
            entry for entry in snapshot.abi_entries
            if entry.semantic_id not in active_set
            and any(item.concept.semantic_id == entry.semantic_id
                    for item in snapshot.concepts)
            and not any(
                row.semantic_id == entry.semantic_id
                and row.source_disposition != "SOURCE_ELIGIBLE"
                for row in snapshot.withheld_rows))
        abi = plan_vocabulary_extension(
            prior, (next_source.semantic_id,), ModelTopologySpecV2())
        mirror = build_registry_mirror_delta(
            prior, abi,
            source_bundle_path=Path(os.environ["BILQIS_A01_SOURCE_BUNDLE"]))
        ast = _load_pinned_released_frame_schemas("boolean", selection)
        lessons = compile_source_constructive_lessons(selection)
        receipt = audit_atlas_authority(
            selection, abi, ast, lessons, mirror)
        self.assertEqual(receipt.source_release_sha256, snapshot.release_sha256)
        self.assertEqual(len(receipt.consumer_bindings), 5)
        self.assertEqual(
            receipt.prior_abi_sha256,
            "30d18c7140d49c168488416e04644b934ea79492561c2b73f65e55be18ed4e8c")
        self.assertIn(
            ("bilqis_mlx/semantics/legacy_abi_v1.json",
             "DECLARED_FORMAL_DOMAIN"),
            receipt.source_dispositions)
        self.assertIn(
            ("bilqis_mlx/semantics/numeric_v1.json",
             "DECLARED_FORMAL_DOMAIN"),
            receipt.source_dispositions)

