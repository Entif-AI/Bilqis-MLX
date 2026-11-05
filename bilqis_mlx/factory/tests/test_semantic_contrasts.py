from __future__ import annotations

from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.semantic_contrasts import (
    AllowedVariation,
    ContrastFamily,
    ContrastSourceFrame,
    ObservationState,
    TemporalStatus,
    check_contrast,
    generate_contrasts,
)
from bilqis_mlx.semantics.frame_schema import (
    BindingState, ConceptRef, FrameSchema, RoleOccurrence, RoleSpec, SourceSpan,
    make_frame_instance,
)

RELEASE = "a" * 64


def concept(name: str, index: int) -> ConceptRef:
    return ConceptRef(f"urn:test:{name}", RELEASE, index, ("Entity",), f"src:{name}")


def source_frame() -> ContrastSourceFrame:
    schema = FrameSchema(
        "test:event", 1, "EVENT",
        (
            RoleSpec("actor", ("Entity",), 1, 2),
            RoleSpec("patient", ("Entity",), 1, 1),
        ),
        "ORDERED", "test-scope",
    )
    frame = make_frame_instance(
        schema,
        source_instance_id="source-001",
        structural_path=(),
        source_span=SourceSpan(0, 20),
        parent_occurrence_id=None,
        bindings=(
            RoleOccurrence("actor", 0, concept=concept("alice", 1)),
            RoleOccurrence("patient", 0, concept=concept("bob", 2)),
        ),
        causal_prefix_end=20,
    )
    return ContrastSourceFrame(
        frame=frame,
        frame_schema=schema,
        semantic_release=RELEASE,
        status=TemporalStatus.OCCURRED,
        observation_state=ObservationState.POSITIVE,
        scope="test-scope",
        negated=False,
        source_morphology="walked",
        authorized_morphology_alternatives=("walks", "walking"),
        checker_revision="test-checker/v1",
    )


class SemanticContrastTests(unittest.TestCase):
    def setUp(self):
        self.source = source_frame()

    def test_role_swap_changes_literal_role_answer_and_preserves_source(self):
        lessons = generate_contrasts(
            self.source, ContrastFamily.ROLE_SWAP, 7,
            (AllowedVariation.role_swap("actor", "patient", query_role="actor"),),
        )
        self.assertEqual(len(lessons), 1)
        lesson = lessons[0]
        self.assertEqual(lesson.expected_answer, "urn:test:bob")
        self.assertEqual(lesson.variant.binding("actor", 0).concept.semantic_id, "urn:test:bob")
        self.assertEqual(self.source.frame.bindings[0].concept.semantic_id, "urn:test:alice")
        self.assertEqual(lesson.lineage.source_occurrence_id, self.source.frame.occurrence_id)
        self.assertNotEqual(lesson.lineage.variant_id, self.source.frame.content_digest)
        self.assertTrue(check_contrast(lesson))

    def test_cardinality_change_has_checker_derived_count(self):
        lessons = generate_contrasts(
            self.source, ContrastFamily.CARDINALITY_CHANGE, 1,
            (AllowedVariation.add_role_value("actor", concept("carol", 3)),),
        )
        self.assertEqual(lessons[0].expected_answer, "2")
        self.assertEqual(tuple(x.occurrence_index for x in lessons[0].variant.bindings if x.role_id == "actor"), (0, 1))
        self.assertTrue(check_contrast(lessons[0]))

    def test_cardinality_removal_reindexes_without_mutating_source(self):
        schema = FrameSchema(
            "test:event", 1, "EVENT",
            (RoleSpec("actor", ("Entity",), 1, 2),
             RoleSpec("patient", ("Entity",), 1, 1)),
            "ORDERED", "test-scope")
        frame = make_frame_instance(
            schema, source_instance_id="source-002", structural_path=(),
            source_span=SourceSpan(0, 20), parent_occurrence_id=None,
            bindings=(
                RoleOccurrence("actor", 0, concept=concept("alice", 1)),
                RoleOccurrence("actor", 1, concept=concept("carol", 3)),
                RoleOccurrence("patient", 0, concept=concept("bob", 2)),
            ), causal_prefix_end=20)
        source = replace(self.source, frame=frame, frame_schema=schema)
        lesson = generate_contrasts(
            source, ContrastFamily.CARDINALITY_CHANGE, 3,
            (AllowedVariation.remove_role_value("actor", 0),),
        )[0]
        self.assertEqual(lesson.expected_answer, "1")
        self.assertEqual(
            tuple((x.role_id, x.occurrence_index, x.concept.semantic_id)
                  for x in lesson.variant.bindings),
            (("actor", 0, "urn:test:carol"), ("patient", 0, "urn:test:bob")),
        )
        self.assertEqual(source.frame.bindings[0].concept.semantic_id, "urn:test:alice")
        self.assertTrue(check_contrast(lesson))

        # A generated projection cannot be smuggled back as a canonical source frame
        # while retaining the original content digest.
        with self.assertRaises(BilqisError):
            replace(source.frame, bindings=lesson.variant.bindings)

    def test_cardinality_and_role_type_authority_fail_closed(self):
        with self.assertRaises(BilqisError):
            generate_contrasts(
                self.source, ContrastFamily.CARDINALITY_CHANGE, 1,
                (AllowedVariation.remove_role_value("actor", 0),),
            )
        too_many = (
            AllowedVariation.add_role_value("actor", concept("carol", 3)),
            AllowedVariation.add_role_value("actor", concept("dave", 4)),
        )
        # Each individual authorized variation starts from source, so one addition is legal.
        self.assertEqual(len(generate_contrasts(
            self.source, ContrastFamily.CARDINALITY_CHANGE, 1, too_many)), 2)
        wrong = ConceptRef("urn:test:number", RELEASE, 5, ("Number",), "src:number")
        with self.assertRaises(BilqisError):
            generate_contrasts(
                self.source, ContrastFamily.CARDINALITY_CHANGE, 1,
                (AllowedVariation.add_role_value("actor", wrong),),
            )

    def test_non_applicable_role_swap_fails_closed(self):
        with self.assertRaises(BilqisError):
            generate_contrasts(
                self.source, ContrastFamily.ROLE_SWAP, 1,
                (AllowedVariation.role_swap("actor", "missing", query_role="actor"),),
            )

    def test_scope_negation_movement_is_structural_not_surface_paraphrase(self):
        variations = (
            AllowedVariation.scope_negation("inner", True, surface_label="not-event-v1"),
            AllowedVariation.scope_negation("inner", True, surface_label="same-meaning-paraphrase"),
        )
        lessons = generate_contrasts(self.source, ContrastFamily.SCOPE_NEGATION, 9, variations)
        self.assertEqual(len(lessons), 1)
        self.assertEqual(lessons[0].expected_answer, "NEGATED@inner")
        self.assertTrue(check_contrast(lessons[0]))

    def test_known_unknown_substitution_produces_unknown_not_guessed_singleton(self):
        lesson = generate_contrasts(
            self.source, ContrastFamily.KNOWN_UNKNOWN, 4,
            (AllowedVariation.unknown_role("patient", 0),),
        )[0]
        binding = lesson.variant.binding("patient", 0)
        self.assertIs(binding.state, BindingState.UNKNOWN)
        self.assertIsNone(binding.concept)
        self.assertEqual(lesson.expected_answer, "UNKNOWN")
        self.assertTrue(check_contrast(lesson))

    def test_planned_occurred_and_missing_negative_are_distinct(self):
        planned = generate_contrasts(
            self.source, ContrastFamily.PLANNED_OCCURRED, 2,
            (AllowedVariation.temporal_status(TemporalStatus.PLANNED),),
        )[0]
        missing = generate_contrasts(
            self.source, ContrastFamily.MISSING_NEGATIVE, 2,
            (AllowedVariation.observation(ObservationState.MISSING),),
        )[0]
        negative = generate_contrasts(
            self.source, ContrastFamily.MISSING_NEGATIVE, 2,
            (AllowedVariation.observation(ObservationState.NEGATIVE),),
        )[0]
        self.assertEqual(planned.expected_answer, "PLANNED")
        self.assertEqual(missing.expected_answer, "MISSING")
        self.assertEqual(negative.expected_answer, "NEGATIVE")
        self.assertNotEqual(missing.lineage.variant_id, negative.lineage.variant_id)
        self.assertTrue(check_contrast(planned))
        self.assertTrue(check_contrast(missing))
        self.assertTrue(check_contrast(negative))

    def test_morphology_alternative_must_be_source_authorized(self):
        lesson = generate_contrasts(
            self.source, ContrastFamily.MORPHOLOGY_ALTERNATIVE, 5,
            (AllowedVariation.morphology("walking"),),
        )[0]
        self.assertEqual(lesson.expected_answer, "walking")
        self.assertTrue(check_contrast(lesson))
        with self.assertRaises(BilqisError):
            generate_contrasts(
                self.source, ContrastFamily.MORPHOLOGY_ALTERNATIVE, 5,
                (AllowedVariation.morphology("invented-form"),),
            )

    def test_seed_reproduces_variant_order_and_disallowed_family_fails_closed(self):
        variations = (
            AllowedVariation.morphology("walks"),
            AllowedVariation.morphology("walking"),
        )
        first = generate_contrasts(self.source, ContrastFamily.MORPHOLOGY_ALTERNATIVE, 123, variations)
        second = generate_contrasts(self.source, ContrastFamily.MORPHOLOGY_ALTERNATIVE, 123, variations)
        self.assertEqual(tuple(x.lineage.variant_id for x in first), tuple(x.lineage.variant_id for x in second))
        self.assertEqual(tuple(x.expected_answer for x in first), tuple(x.expected_answer for x in second))
        with self.assertRaises(BilqisError):
            generate_contrasts(
                self.source, ContrastFamily.ROLE_SWAP, 1,
                (AllowedVariation.morphology("walks"),),
            )

    def test_checker_rejects_tampered_gold_without_trusting_generator(self):
        lesson = generate_contrasts(
            self.source, ContrastFamily.ROLE_SWAP, 7,
            (AllowedVariation.role_swap("actor", "patient", query_role="actor"),),
        )[0]
        self.assertFalse(check_contrast(replace(lesson, expected_answer="urn:test:alice")))


if __name__ == "__main__":
    unittest.main()
