"""A12 F17 held-gloss adversary across semantic and teacher surfaces."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.skos_curriculum import (
    LearnedFrontier, SOURCE_FAMILY_ADAPTERS,
    _compile_semantic_curriculum_snapshot,
    _compile_source_constructive_lessons_snapshot,
)
from bilqis_mlx.factory.tests.test_skos_curriculum import _snapshot
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2
from bilqis_mlx.semantics.atlas.vocabulary import VocabularyPrior, plan_vocabulary_extension
from bilqis_mlx.semantics.atlas_features import (
    FeatureSchema, build_feature_manifest, plan_prospective_identity_features,
)
from bilqis_mlx.semantics.atlas_projection import (
    AtlasLabel, SHAPE_POLICY,
    _canonical_bytes as _atlas_bytes, _digest as _atlas_sha256,
)
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection


def _held_gloss_fixture():
    original = replace(
        _snapshot(), shape_policy_sha256=_atlas_sha256(_atlas_bytes(SHAPE_POLICY)))
    held = next(row for row in original.withheld_rows
                if row.source_disposition == "SOURCE_HELD")
    admitted = original.concepts[0]
    renamed = replace(
        admitted, concept=replace(
            admitted.concept,
            labels=(AtlasLabel("altLabel", "near synonym"),
                    AtlasLabel("prefLabel", "plausible English gloss matching the held source"))))
    return original, replace(original, concepts=(renamed, *original.concepts[1:])), held


def _prior(snapshot, features):
    active = tuple(entry.semantic_id for entry in snapshot.abi_entries if entry.active)
    active_indices = tuple(sorted(entry.index for entry in snapshot.abi_entries if entry.active))
    bank_count = max(
        1, max(active_indices, default=0) // ModelTopologySpecV2.semantic_bank_rows + 1)
    return VocabularyPrior(
        AtlasArtifactSelection(
            "fixture", snapshot.bundle_id, snapshot.release_sha256,
            snapshot.source_bundle_id),
        GenerationExtents(
            bank_count, 1, _atlas_sha256(_atlas_bytes(list(active_indices))),
            "b" * 64, features.digest),
        features, FeatureSchema((), ()), active, "e" * 64)


class AtlasHeldGlossAuthorityTests(unittest.TestCase):
    def _assert_semantic_refusal(self, snapshot, held):
        self.assertNotIn(held.semantic_id,
                         {entry.semantic_id for entry in snapshot.abi_entries})
        features = build_feature_manifest(snapshot, FeatureSchema((), ()))
        self.assertIn((held.semantic_id, held.reason_code), features.held_reasons)
        with self.assertRaises(BilqisError) as caught:
            features.features_for(held.semantic_id, "UNKNOWN", "UNKNOWN", "task:held")
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_FEATURE_CONCEPT_NOT_ADMITTED")
        self.assertEqual(caught.exception.context["source_reason_codes"],
                         (held.reason_code,))
        with self.assertRaises(BilqisError) as caught:
            plan_prospective_identity_features(
                snapshot, features, (held.semantic_id,),
                expected_feature_digest=features.digest)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_FEATURE_PROSPECTIVE_SOURCE_HELD")
        self.assertEqual(caught.exception.context["source_reason_codes"],
                         (held.reason_code,))
        with patch(
            "bilqis_mlx.semantics.atlas.vocabulary_planning.load_pinned_atlas_snapshot",
            return_value=snapshot), self.assertRaises(BilqisError) as caught:
            plan_vocabulary_extension(
                _prior(snapshot, features), (held.semantic_id,), ModelTopologySpecV2())
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_FEATURE_PROSPECTIVE_SOURCE_HELD")
        self.assertEqual(caught.exception.context["source_reason_codes"],
                         (held.reason_code,))

    def _assert_teacher_refusal(self, snapshot, held):
        source_lessons = _compile_source_constructive_lessons_snapshot(snapshot).lessons
        lesson_set = _compile_source_constructive_lessons_snapshot(snapshot)
        self.assertFalse(any(
            held.semantic_id in (lesson.semantic_id, *lesson.constituents,
                                 *lesson.prerequisite_closure)
            for lesson in source_lessons))
        factory_hold = next(row for row in lesson_set.source_holds
                            if row.semantic_id == held.semantic_id)
        self.assertEqual((factory_hold.reason_code, factory_hold.owner),
                         (held.reason_code, held.owner))
        teacher = _compile_semantic_curriculum_snapshot(
            snapshot, SOURCE_FAMILY_ADAPTERS,
            LearnedFrontier(snapshot.release_sha256,
                            claimed_exposed=(held.semantic_id,),
                            claimed_qualified=(held.semantic_id,)))
        self.assertNotIn(held.semantic_id, teacher.source_eligible_concept_ids)
        self.assertFalse(any(
            held.semantic_id in (lesson.semantic_id, *lesson.constituents,
                                 *lesson.prerequisite_closure)
            for lesson in teacher.source_lessons))
        source_hold = next(row for row in teacher.source_hold_rows
                           if row.semantic_id == held.semantic_id)
        self.assertEqual((source_hold.reason_code, source_hold.owner),
                         (held.reason_code, held.owner))

    def test_held_gloss_cannot_promote_and_keeps_source_reason(self):
        original, relabeled, held = _held_gloss_fixture()
        for snapshot in (original, relabeled):
            with self.subTest(labels=snapshot.concepts[0].concept.labels):
                self._assert_semantic_refusal(snapshot, held)
                self._assert_teacher_refusal(snapshot, held)


if __name__ == "__main__":
    unittest.main()
