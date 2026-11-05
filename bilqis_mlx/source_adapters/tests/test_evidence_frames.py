from __future__ import annotations

from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.source_adapters.evidence_frames import (
    PUBLIC_FIXTURE_SOURCE,
    BamfEvidenceSnapshot,
    EvidenceRecord,
    EvidenceRights,
    EventTime,
    ReportedValue,
    SourceSpan,
    build_public_fixture_snapshot,
    parse_public_fixture_source,
    public_export,
)
from bilqis_mlx.factory.evidence_curriculum import (
    EvidenceLessonStatus,
    compile_typed_reconstructions,
    compile_evidence_lessons,
    plan_fresh_challenge,
    split_evidence_families,
)


RELEASE = "a" * 64
STUDY = "LEXSENSE-24e0d37974513f"
HOUR = "fixture:admitted-unit:hour"
AGENT = "AG-7ebd45a9797f21"


class EvidenceFrameTests(unittest.TestCase):
    def setUp(self):
        self.snapshot, self.rights = build_public_fixture_snapshot(
            semantic_release=RELEASE,
            category_ref=STUDY,
            hour_unit_ref=HOUR,
            agent_role_ref=AGENT,
        )

    def test_public_fixture_is_parsed_from_exact_source_bytes(self):
        record = parse_public_fixture_source(
            PUBLIC_FIXTURE_SOURCE, category_ref=STUDY, hour_unit_ref=HOUR,
            agent_role_ref=AGENT)
        self.assertEqual(record.actor_ref, "actor_01")
        self.assertEqual(record.category_label, "study")
        self.assertEqual(record.status, "COMPLETED")
        self.assertEqual(record.reported_value.decimal, "0.25")
        self.assertEqual(record.unit_label, "h")
        self.assertEqual(record.source_span, SourceSpan(0, len(PUBLIC_FIXTURE_SOURCE)))
        with self.assertRaises(BilqisError):
            parse_public_fixture_source(
                PUBLIC_FIXTURE_SOURCE.replace("completed", "maybe"),
                category_ref=STUDY, hour_unit_ref=HOUR, agent_role_ref=AGENT)

    def test_literal_public_fixture_compiles_source_linked_exact_lessons(self):
        result = compile_evidence_lessons(self.snapshot, self.rights, RELEASE)
        self.assertEqual(result.holds, ())
        self.assertEqual(len(result.lessons), 4)
        self.assertEqual(result.lessons[0].rendered, "actor_01 completed study for 0.25 h.")
        self.assertEqual(result.lessons[0].source_span, SourceSpan(0, len(PUBLIC_FIXTURE_SOURCE)))
        self.assertEqual(result.lessons[0].frame.actor_role_ref, AGENT)
        self.assertEqual(result.lessons[0].frame.category_ref, STUDY)
        self.assertEqual(result.lessons[0].frame.status, "COMPLETED")
        self.assertEqual(result.lessons[0].frame.reported_decimal, "0.25")
        self.assertEqual(result.lessons[0].frame.reported_unit_ref, HOUR)
        self.assertEqual(result.lessons[0].rights, self.rights)
        self.assertEqual(result.lessons[0].frame.occurrence_truth, "TRUE")
        self.assertEqual(result.lessons[3].question, "Convert the reported duration to minutes.")
        self.assertEqual(result.lessons[3].gold, "15")
        self.assertEqual(result.lessons[3].derivation.operator_id, "duration.hour-to-minute/v1")
        self.assertTrue(all(lesson.check() for lesson in result.lessons))

    def test_exact_hour_conversion_preserves_trailing_zero_magnitude(self):
        record = replace(
            self.snapshot.records[0], reported_value=ReportedValue("1", HOUR))
        result = compile_evidence_lessons(
            replace(self.snapshot, records=(record,)), self.rights, RELEASE)
        self.assertEqual(result.lessons[3].gold, "60")
        self.assertTrue(result.lessons[3].check())

    def test_planned_and_unknown_duration_are_distinct_from_completed_and_zero(self):
        record = self.snapshot.records[0]
        planned = replace(record, status="PLANNED")
        planned_snapshot = replace(self.snapshot, records=(planned,))
        planned_result = compile_evidence_lessons(planned_snapshot, self.rights, RELEASE)
        self.assertEqual(planned_result.lessons[0].rendered, "actor_01 plans study for 0.25 h.")
        self.assertEqual(planned_result.lessons[1].gold, "PLANNED")
        self.assertEqual(planned_result.lessons[0].frame.occurrence_truth, "UNKNOWN")

        unknown = replace(record, reported_value=ReportedValue(None, HOUR))
        unknown_result = compile_evidence_lessons(
            replace(self.snapshot, records=(unknown,)), self.rights, RELEASE)
        self.assertEqual(
            unknown_result.lessons[0].rendered,
            "actor_01 reported study; duration is unknown.",
        )
        self.assertEqual(unknown_result.lessons[2].gold, "UNKNOWN")
        self.assertEqual(unknown_result.lessons[3].gold, "UNKNOWN")

        zero = replace(record, reported_value=ReportedValue("0", HOUR))
        zero_result = compile_evidence_lessons(
            replace(self.snapshot, records=(zero,)), self.rights, RELEASE)
        self.assertEqual(zero_result.lessons[2].gold, "0")
        self.assertEqual(zero_result.lessons[3].gold, "0")

    def test_contradictory_dates_preserve_alternatives_instead_of_inventing_chronology(self):
        record = replace(
            self.snapshot.records[0],
            event_time=EventTime(
                "2026-01-02T10:00:00Z", "2026-01-02T09:00:00Z", "UTC"),
            alternatives=("EVENT_TIME_CONTRADICTORY",),
        )
        result = compile_evidence_lessons(
            replace(self.snapshot, records=(record,)), self.rights, RELEASE)
        self.assertEqual(result.lessons[0].frame.event_time.start_iso, "2026-01-02T10:00:00Z")
        self.assertEqual(result.lessons[0].frame.event_time.end_iso, "2026-01-02T09:00:00Z")
        self.assertEqual(result.lessons[0].frame.alternatives, ("EVENT_TIME_CONTRADICTORY",))

    def test_typed_reconstruction_preserves_reported_computed_negation_and_alternatives(self):
        source = self.snapshot.records[0]
        record = replace(
            source,
            negated=True,
            alternatives=("EVENT_TIME_DISPUTED", "ALTERNATE_INTERPRETATION"),
        )
        result = compile_evidence_lessons(
            replace(self.snapshot, records=(record,)), self.rights, RELEASE)
        reconstruction = compile_typed_reconstructions(result)[0]
        self.assertEqual(reconstruction.reported_value, "0.25")
        self.assertEqual(reconstruction.reported_unit_ref, HOUR)
        self.assertEqual(reconstruction.computed_values[0].output_value, "15")
        self.assertTrue(reconstruction.negated)
        self.assertEqual(reconstruction.template_lineage, "T1N")
        self.assertEqual(
            result.lessons[0].rendered,
            "actor_01 did not complete study for 0.25 h.",
        )
        self.assertEqual(result.lessons[0].frame.occurrence_truth, "UNKNOWN")
        self.assertEqual(
            reconstruction.alternatives,
            ("EVENT_TIME_DISPUTED", "ALTERNATE_INTERPRETATION"),
        )

        unambiguous = compile_evidence_lessons(
            replace(self.snapshot, records=(replace(source, negated=True),)),
            self.rights,
            RELEASE,
        )
        self.assertEqual(unambiguous.lessons[0].frame.occurrence_truth, "FALSE")

    def test_private_or_unclassified_material_is_rejected_before_public_export(self):
        for regime in ("PRIVATE_REAL", "UNCLASSIFIED"):
            with self.subTest(regime=regime):
                rights = replace(self.rights, regime=regime, public_export_allowed=False)
                private_record = replace(
                    self.snapshot.records[0], actor_ref="PROTECTED_SENTINEL_DO_NOT_EXPORT")
                snapshot = replace(self.snapshot, rights=rights, records=(private_record,))
                result = compile_evidence_lessons(snapshot, rights, RELEASE)
                self.assertNotIn("PROTECTED_SENTINEL_DO_NOT_EXPORT", repr(result))
                self.assertEqual(result.lessons, ())
                self.assertEqual(result.holds[0].status, EvidenceLessonStatus.SOURCE_HELD)
                with self.assertRaises(BilqisError) as caught:
                    public_export(result)
                self.assertEqual(
                    caught.exception.context["reason"],
                    "BAMF_EVIDENCE_PUBLIC_EXPORT_HELD",
                )

    def test_paraphrases_of_one_episode_cannot_cross_independent_split(self):
        original = self.snapshot.records[0]
        sibling = replace(original, record_id="fixture-001-paraphrase")
        same_family = replace(self.snapshot, records=(original, sibling))
        result = compile_evidence_lessons(same_family, self.rights, RELEASE)
        with self.assertRaises(ValueError):
            split_evidence_families(
                result, train_record_ids=(original.record_id,),
                heldout_record_ids=(sibling.record_id,))

        same_side = split_evidence_families(
            result, train_record_ids=(original.record_id, sibling.record_id),
            heldout_record_ids=())
        self.assertEqual(len(same_side.train_family_ids), 1)

        other = replace(
            original,
            record_id="fixture-002",
            adjudication_ref="adjudication:fixture-002",
            source_span=SourceSpan(0, len(PUBLIC_FIXTURE_SOURCE)),
        )
        independent = compile_evidence_lessons(
            replace(self.snapshot, records=(original, other)), self.rights, RELEASE)
        receipt = split_evidence_families(
            independent, train_record_ids=(original.record_id,),
            heldout_record_ids=(other.record_id,))
        self.assertNotEqual(receipt.train_family_ids, receipt.heldout_family_ids)

    def test_fresh_challenge_splits_source_families_before_template_groups(self):
        original = self.snapshot.records[0]
        paraphrase = replace(original, record_id="fixture-001-paraphrase")
        other = replace(
            original,
            record_id="fixture-002",
            adjudication_ref="adjudication:fixture-002",
        )
        result = compile_evidence_lessons(
            replace(self.snapshot, records=(original, paraphrase, other)),
            self.rights,
            RELEASE,
        )
        with self.assertRaises(ValueError):
            plan_fresh_challenge(
                result,
                train_record_ids=(original.record_id,),
                heldout_record_ids=(paraphrase.record_id,),
            )

        plan = plan_fresh_challenge(
            result,
            train_record_ids=(original.record_id, paraphrase.record_id),
            heldout_record_ids=(other.record_id,),
        )
        self.assertEqual(len(plan.split.train_family_ids), 1)
        self.assertEqual(len(plan.split.heldout_family_ids), 1)
        self.assertEqual(plan.train_template_groups[0][1], "T1")
        self.assertEqual(plan.heldout_template_groups[0][1], "T1")
        self.assertEqual(
            set(plan.post_exam_teachable_lesson_ids),
            {lesson.lesson_id for lesson in result.lessons
             if lesson.record_id == other.record_id},
        )

    def test_unadjudicated_record_is_held_without_blocking_qualified_sibling(self):
        qualified = self.snapshot.records[0]
        held = replace(qualified, record_id="fixture-held", adjudication_ref=None)
        result = compile_evidence_lessons(
            replace(self.snapshot, records=(qualified, held)), self.rights, RELEASE)
        self.assertEqual(len(result.lessons), 4)
        self.assertEqual(tuple(item.record_id for item in result.holds), ("fixture-held",))
        self.assertEqual(result.holds[0].reason, "SOURCE_UNADJUDICATED")
        self.assertIs(public_export(result), result)

    def test_interpretation_revision_changes_dependent_lessons_not_episode_identity(self):
        first = compile_evidence_lessons(self.snapshot, self.rights, RELEASE)
        corrected = replace(self.snapshot, interpretation_revision="bravo-public-fixture/v2")
        second = compile_evidence_lessons(corrected, self.rights, RELEASE)
        self.assertEqual(
            {lesson.source_family_id for lesson in first.lessons},
            {lesson.source_family_id for lesson in second.lessons},
        )
        self.assertNotEqual(
            {lesson.lesson_id for lesson in first.lessons},
            {lesson.lesson_id for lesson in second.lessons},
        )
        self.assertEqual(
            {lesson.frame.category_ref for lesson in first.lessons},
            {lesson.frame.category_ref for lesson in second.lessons},
        )

    def test_missing_report_is_verification_needed_not_nonoccurrence(self):
        record = replace(
            self.snapshot.records[0],
            status="PLANNED",
            reported_value=ReportedValue(None, HOUR),
            alternatives=("EXPECTED_REPORT_MISSING",),
        )
        result = compile_evidence_lessons(
            replace(self.snapshot, records=(record,)), self.rights, RELEASE)
        self.assertEqual(result.lessons[0].frame.verification_state, "VERIFICATION_NEEDED")
        self.assertNotIn("NON_OCCURRENCE", result.lessons[0].frame.alternatives)


if __name__ == "__main__":
    unittest.main()
