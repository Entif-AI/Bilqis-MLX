"""A12.3 literal SOURCE_HELD row-staging and teacher-target boundaries."""
from dataclasses import replace
import unittest
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.runtime.tests.batch import test_atlas_training_adapter as training_fixture
from bilqis_mlx.semantics.atlas.vocabulary import (
    VocabularyBankParent,
    apply_vocabulary_extension,
    plan_vocabulary_extension,
)
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas_projection import BANK_SIZE
from bilqis_mlx.semantics.frame_schema import ConceptRef, FrameTree
from bilqis_mlx.semantics.tests.test_atlas_release_held_gloss import (
    _held_gloss_fixture,
    _prior,
)


def _bank_parent(snapshot, features):
    prior = _prior(snapshot, features)
    empty = mx.zeros(
        (BANK_SIZE, ModelTopologySpecV2.width), dtype=mx.float32)
    active_indices = tuple(
        snapshot.abi_for_semantic(name).index
        for name in prior.active_semantic_ids)
    return VocabularyBankParent(
        prior,
        tuple(empty for _ in range(prior.extents.semantic_bank_count)),
        tuple(empty for _ in range(prior.extents.semantic_bank_count)),
        tuple(empty for _ in range(prior.extents.semantic_bank_count)),
        tuple((index, 0) for index in active_indices),
        {},
        0,
        0,
    )


class AtlasHeldBoundaryTests(unittest.TestCase):
    def test_held_identity_never_reaches_trainable_row_staging(self):
        _original, snapshot, held = _held_gloss_fixture()
        features = build_feature_manifest(snapshot, FeatureSchema((), ()))
        parent = _bank_parent(snapshot, features)
        active = set(parent.prior.active_semantic_ids)
        candidate = next(
            entry.semantic_id for entry in snapshot.abi_entries
            if not entry.active and entry.semantic_id not in active)

        with patch(
                "bilqis_mlx.semantics.atlas.vocabulary_planning."
                "load_pinned_atlas_snapshot",
                return_value=snapshot):
            valid = plan_vocabulary_extension(
                parent.prior, (candidate,), ModelTopologySpecV2())
        forged = replace(
            valid,
            allocations=(
                replace(valid.allocations[0], semantic_id=held.semantic_id),),
        )

        with patch(
                "bilqis_mlx.semantics.atlas.vocabulary_planning."
                "load_pinned_atlas_snapshot",
                return_value=snapshot), patch(
                    "bilqis_mlx.semantics.atlas.vocabulary_staging."
                    "_stage_extension_rows") as stage_rows:
            with self.assertRaises(BilqisError) as caught:
                apply_vocabulary_extension(parent, forged)

        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_FEATURE_PROSPECTIVE_SOURCE_HELD")
        self.assertEqual(
            caught.exception.context["source_reason_codes"],
            (held.reason_code,))
        stage_rows.assert_not_called()

    def test_held_identity_refuses_before_teacher_target_construction(self):
        _original, snapshot, held = _held_gloss_fixture()
        features = build_feature_manifest(snapshot, FeatureSchema((), ()))
        features = replace(
            features,
            semantic_release="0" * 64,
            role_map=(("subject", 1),),
            schema_map=(("fixture:training-frame", 1),),
        )
        fixture = training_fixture.AtlasTrainingAdapterTest(
            "test_cross_source_ast_and_frame_substitution_is_rejected")
        fixture.setUp()
        original_builder = training_fixture.source_ast_for

        def held_ast(tokens, release="fixture-release", graph=None):
            ast = original_builder(tokens, release, graph)
            concept = ConceptRef(
                held.semantic_id,
                "0" * 64,
                0,
                ("Entity",),
                ast.source_instance_id,
            )
            root = ast.frames[0].root
            frame = training_fixture.make_frame_instance(
                training_fixture._training_schema(),
                source_instance_id=ast.source_instance_id,
                structural_path=(),
                source_span=root.source_span,
                parent_occurrence_id=None,
                bindings=(training_fixture.RoleOccurrence(
                    "subject", 0, concept=concept),),
                causal_prefix_end=root.causal_prefix_end,
            )
            return replace(ast, frames=(FrameTree(frame),))

        try:
            with patch.object(
                    training_fixture, "source_ast_for",
                    side_effect=held_ast), patch.object(
                        training_fixture, "_atlas_features",
                        return_value=features), patch(
                            "bilqis_mlx.runtime.atlas_training_adapter."
                            "BamfTarget") as target:
                with self.assertRaises(BilqisError) as caught:
                    fixture.compile(fixture.rows)
        finally:
            fixture.doCleanups()

        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_FEATURE_CONCEPT_NOT_ADMITTED")
        self.assertEqual(
            caught.exception.context["source_reason_codes"],
            (held.reason_code,))
        target.assert_not_called()


if __name__ == "__main__":
    unittest.main()
