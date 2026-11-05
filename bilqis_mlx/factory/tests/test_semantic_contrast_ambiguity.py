from __future__ import annotations

from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.semantic_contrasts import (
    MAX_AMBIGUITY_INTERPRETATIONS,
    AllowedVariation,
    ContrastFamily,
    NoiseSignature,
    apply_presentation_noise,
    explore_ambiguity,
    generate_contrasts,
)
from bilqis_mlx.factory.tests.test_semantic_contrasts import concept, source_frame


class SemanticContrastAmbiguityTests(unittest.TestCase):
    def setUp(self):
        self.source = source_frame()

    def test_ambiguity_is_bounded_ranked_and_reproducible(self):
        variations = tuple(
            AllowedVariation.add_role_value("actor", concept(f"candidate-{index}", index + 10))
            for index in range(6)
        )
        first = explore_ambiguity(
            self.source,
            ContrastFamily.CARDINALITY_CHANGE,
            41,
            variations,
        )
        second = explore_ambiguity(
            self.source,
            ContrastFamily.CARDINALITY_CHANGE,
            41,
            variations,
        )
        self.assertEqual(len(first.interpretations), MAX_AMBIGUITY_INTERPRETATIONS)
        self.assertEqual(first, second)
        self.assertEqual(
            tuple(item.lineage.variant_id for item in first.interpretations),
            tuple(item.lineage.variant_id for item in second.interpretations),
        )

    def test_unresolved_interpretations_preserve_alternative_target(self):
        variations = (
            AllowedVariation.morphology("walks"),
            AllowedVariation.morphology("walking"),
        )
        result = explore_ambiguity(
            self.source,
            ContrastFamily.MORPHOLOGY_ALTERNATIVE,
            7,
            variations,
        )
        self.assertTrue(result.target.unresolved)
        self.assertEqual(
            set(result.target.answers),
            {"walks", "walking"},
        )

        chosen = result.interpretations[0]
        resolved = explore_ambiguity(
            self.source,
            ContrastFamily.MORPHOLOGY_ALTERNATIVE,
            7,
            variations,
            decisive_variant_id=chosen.lineage.variant_id,
        )
        self.assertFalse(resolved.target.unresolved)
        self.assertEqual(resolved.target.answers, (chosen.expected_answer,))

    def test_decision_must_name_one_of_the_bounded_interpretations(self):
        with self.assertRaises(BilqisError):
            explore_ambiguity(
                self.source,
                ContrastFamily.MORPHOLOGY_ALTERNATIVE,
                5,
                (AllowedVariation.morphology("walking"),),
                decisive_variant_id="f" * 64,
            )

    def test_noise_changes_presentation_not_canonical_identity_or_gold(self):
        lesson = generate_contrasts(
            self.source,
            ContrastFamily.ROLE_SWAP,
            7,
            (AllowedVariation.role_swap("actor", "patient", query_role="actor"),),
        )[0]
        signature = NoiseSignature("MASK_TEXT", "question", 5, 17)
        noisy = apply_presentation_noise(lesson, signature)
        repeated = apply_presentation_noise(lesson, signature)
        self.assertEqual(noisy, repeated)
        self.assertNotEqual(noisy.presented_question, lesson.question)
        self.assertEqual(noisy.lesson.source, lesson.source)
        self.assertEqual(noisy.lesson.variant, lesson.variant)
        self.assertEqual(noisy.lesson.lineage, lesson.lineage)
        self.assertEqual(noisy.lesson.expected_answer, lesson.expected_answer)

    def test_noise_signature_identifies_distinct_weakness_not_surface_rewording(self):
        lesson = generate_contrasts(
            self.source,
            ContrastFamily.MORPHOLOGY_ALTERNATIVE,
            3,
            (AllowedVariation.morphology("walking"),),
        )[0]
        first = apply_presentation_noise(
            lesson, NoiseSignature("MASK_TEXT", "question", 3, 1))
        second = apply_presentation_noise(
            lesson, NoiseSignature("MASK_TEXT", "question", 4, 1))
        self.assertEqual(first.lesson.lineage.variant_id, second.lesson.lineage.variant_id)
        self.assertNotEqual(first.signature.signature_sha256, second.signature.signature_sha256)
        self.assertNotEqual(first.weakness_id, second.weakness_id)

        paraphrased = replace(lesson, question=lesson.question + " Please answer.")
        same_signature = apply_presentation_noise(paraphrased, first.signature)
        self.assertEqual(first.weakness_id, same_signature.weakness_id)

    def test_noise_fails_closed_outside_presentation_surface(self):
        lesson = generate_contrasts(
            self.source,
            ContrastFamily.MORPHOLOGY_ALTERNATIVE,
            3,
            (AllowedVariation.morphology("walking"),),
        )[0]
        with self.assertRaises(BilqisError):
            apply_presentation_noise(
                lesson, NoiseSignature("MASK_TEXT", "canonical-gold", 1, 0))


if __name__ == "__main__":
    unittest.main()
