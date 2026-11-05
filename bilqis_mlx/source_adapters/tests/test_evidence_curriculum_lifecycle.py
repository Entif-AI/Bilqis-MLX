"""A10 evidence lifecycle, correction, and privacy-boundary regressions."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.evidence_curriculum import (
    EvidenceLessonStatus,
    compile_evidence_lessons,
    compile_typed_reconstructions,
    plan_fresh_challenge,
)
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.source_adapters.evidence_frames import (
    EvidenceSemanticAuthority,
    EventTime,
    build_public_fixture_snapshot,
    public_export,
)
from bilqis_mlx.source_adapters.tests.test_evidence_frames import (
    AGENT, HOUR, RELEASE, STUDY,
)


class EvidenceCurriculumLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.selection = AtlasArtifactSelection(
            "synthetic:test-atlas", "b" * 64, RELEASE, "c" * 64)
        authority = EvidenceSemanticAuthority(
            RELEASE, STUDY, HOUR, AGENT, "UNIT_CONVERT",
            "059ccd2a33330473973914b94fc0d772d6f845b6ee9c8e736f1876e6a9823e9f")
        self._source_authority = patch(
            "bilqis_mlx.source_adapters.evidence_frames."
            "resolve_public_fixture_authority",
            return_value=authority)
        self._source_authority.start()
        self.addCleanup(self._source_authority.stop)
        self.snapshot, self.rights = build_public_fixture_snapshot(
            atlas_selection=self.selection)

    def compile(self, snapshot=None, rights=None):
        return compile_evidence_lessons(
            self.snapshot if snapshot is None else snapshot,
            self.rights if rights is None else rights,
            RELEASE)

    def test_contradictory_dates_preserve_alternatives_instead_of_inventing_chronology(self):
        record = replace(
            self.snapshot.records[0],
            event_time=EventTime(
                "2026-01-02T10:00:00Z", "2026-01-02T09:00:00Z", "UTC"),
            alternatives=("EVENT_TIME_CONTRADICTORY",),
        )
        result = self.compile(replace(self.snapshot, records=(record,)))
        self.assertEqual(result.lessons[0].frame.event_time.start_iso,
                         "2026-01-02T10:00:00Z")
        self.assertEqual(result.lessons[0].frame.event_time.end_iso,
                         "2026-01-02T09:00:00Z")
        self.assertEqual(result.lessons[0].frame.alternatives,
                         ("EVENT_TIME_CONTRADICTORY",))

    def test_typed_reconstruction_preserves_reported_computed_negation_and_alternatives(self):
        source = self.snapshot.records[0]
        record = replace(
            source, negated=True,
            alternatives=("EVENT_TIME_DISPUTED", "ALTERNATE_INTERPRETATION"))
        result = self.compile(replace(self.snapshot, records=(record,)))
        reconstruction = compile_typed_reconstructions(result)[0]
        self.assertEqual(reconstruction.reported_value, "0.25")
        self.assertEqual(reconstruction.reported_unit_ref, HOUR)
        self.assertEqual(reconstruction.computed_values[0].output_value, "15")
        self.assertTrue(reconstruction.negated)
        self.assertEqual(reconstruction.template_lineage, "T1N")
        self.assertEqual(result.lessons[0].frame.occurrence_truth, "UNKNOWN")
        self.assertEqual(
            reconstruction.alternatives,
            ("EVENT_TIME_DISPUTED", "ALTERNATE_INTERPRETATION"))
        unambiguous = self.compile(
            replace(self.snapshot, records=(replace(source, negated=True),)))
        self.assertEqual(unambiguous.lessons[0].frame.occurrence_truth, "FALSE")

    def test_private_real_reaches_trainer_preparation_but_cannot_export(self):
        rights = replace(
            self.rights, regime="PRIVATE_REAL", public_export_allowed=False)
        private_record = replace(
            self.snapshot.records[0], actor_ref="PROTECTED_SENTINEL_DO_NOT_EXPORT")
        snapshot = replace(self.snapshot, rights=rights, records=(private_record,))
        result = self.compile(snapshot, rights)
        self.assertEqual(len(result.lessons), 4)
        self.assertEqual(result.holds, ())
        self.assertTrue(all(lesson.check() for lesson in result.lessons))

        prepared = compile_typed_reconstructions(result)
        self.assertEqual(prepared[0].actor_ref, "PROTECTED_SENTINEL_DO_NOT_EXPORT")
        self.assertEqual(prepared[0].rights, rights)
        self.assertEqual(
            prepared[0].interpretation_revision, snapshot.interpretation_revision)
        with self.assertRaises(BilqisError) as caught:
            public_export(prepared[0])
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_EVIDENCE_PUBLIC_EXPORT_FORBIDDEN")

        challenge = plan_fresh_challenge(
            result, train_record_ids=(private_record.record_id,),
            heldout_record_ids=())
        self.assertEqual(challenge.split.train_record_ids,
                         (private_record.record_id,))
        self.assertEqual(challenge.rights, rights)
        self.assertEqual(challenge.split.rights, rights)
        self.assertEqual(
            challenge.interpretation_revision, snapshot.interpretation_revision)
        self.assertEqual(
            challenge.split.interpretation_revision, snapshot.interpretation_revision)
        for derivative in (challenge, challenge.split):
            with self.assertRaises(BilqisError) as caught:
                public_export(derivative)
            self.assertEqual(
                caught.exception.context["reason"],
                "BAMF_EVIDENCE_PUBLIC_EXPORT_FORBIDDEN")
        with self.assertRaises(BilqisError) as caught:
            public_export(result)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_EVIDENCE_PUBLIC_EXPORT_FORBIDDEN")

    def test_unclassified_material_is_held_before_training_or_export(self):
        rights = replace(
            self.rights, regime="UNCLASSIFIED", public_export_allowed=False)
        record = replace(
            self.snapshot.records[0], actor_ref="UNCLASSIFIED_SENTINEL_DO_NOT_EXPORT")
        snapshot = replace(self.snapshot, rights=rights, records=(record,))
        result = self.compile(snapshot, rights)
        self.assertNotIn("UNCLASSIFIED_SENTINEL_DO_NOT_EXPORT", repr(result))
        self.assertEqual(result.lessons, ())
        self.assertEqual(result.holds[0].status, EvidenceLessonStatus.SOURCE_HELD)
        with self.assertRaises(BilqisError) as caught:
            public_export(result)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_EVIDENCE_PUBLIC_EXPORT_HELD")

    def test_unadjudicated_record_is_held_without_blocking_qualified_sibling(self):
        qualified = self.snapshot.records[0]
        held = replace(qualified, record_id="fixture-held", adjudication_ref=None)
        result = self.compile(replace(self.snapshot, records=(qualified, held)))
        self.assertEqual(len(result.lessons), 4)
        self.assertEqual(tuple(item.record_id for item in result.holds),
                         ("fixture-held",))
        self.assertEqual(result.holds[0].reason, "SOURCE_UNADJUDICATED")
        self.assertIs(public_export(result), result)

    def test_interpretation_revision_changes_dependent_lessons_not_episode_identity(self):
        first = self.compile()
        corrected = replace(
            self.snapshot, interpretation_revision="bravo-public-fixture/v2")
        second = self.compile(corrected)
        self.assertEqual(
            {lesson.source_family_id for lesson in first.lessons},
            {lesson.source_family_id for lesson in second.lessons})
        self.assertNotEqual(
            {lesson.lesson_id for lesson in first.lessons},
            {lesson.lesson_id for lesson in second.lessons})
        self.assertEqual(
            {lesson.frame.category_ref for lesson in first.lessons},
            {lesson.frame.category_ref for lesson in second.lessons})


if __name__ == "__main__":
    unittest.main()
