from __future__ import annotations

from dataclasses import replace
import inspect
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.source_adapters.tests._evidence_cases import (
    EvidenceFamilyAuthorityCases,
)
from bilqis_mlx.source_adapters.evidence.evidence_frames import (
    LEGACY_PUBLIC_FIXTURE_MANIFEST_CID,
    PUBLIC_FIXTURE_SOURCE,
    BamfEvidenceSnapshot,
    EvidenceSemanticAuthority,
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
    EvidenceLesson,
    EvidenceLessonStatus,
    compile_typed_reconstructions,
    compile_evidence_lessons,
    plan_fresh_challenge,
    split_evidence_families,
)


RELEASE = "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306"
STUDY = (
    "https://github.com/Entif-AI/Bilqis-MLX/id/sense/"
    "NI-LEXICON-CURRICULUM/LEXROOT-3e51e33b4a970f/STEM%203/BSC"
)
HOUR = "h"
AGENT = "agent"


class EvidenceFrameTests(EvidenceFamilyAuthorityCases, unittest.TestCase):
    def setUp(self):
        self.selection = AtlasArtifactSelection(
            "synthetic:test-atlas", "b" * 64, RELEASE, "c" * 64)
        authority = EvidenceSemanticAuthority(
            RELEASE, STUDY, HOUR, AGENT, "UNIT_CONVERT",
            "059ccd2a33330473973914b94fc0d772d6f845b6ee9c8e736f1876e6a9823e9f")
        self._source_authority = patch(
            "bilqis_mlx.source_adapters.evidence.evidence_frames."
            "resolve_public_fixture_authority",
            return_value=authority)
        self._source_authority.start()
        self.addCleanup(self._source_authority.stop)
        self.snapshot, self.rights = build_public_fixture_snapshot(
            atlas_selection=self.selection,
        )

    def compile(self, snapshot=None, rights=None):
        return compile_evidence_lessons(
            self.snapshot if snapshot is None else snapshot,
            self.rights if rights is None else rights,
            RELEASE)

    def test_public_curriculum_api_keeps_facade_module_identity(self):
        self.assertEqual(
            EvidenceLesson.__module__, "bilqis_mlx.factory.evidence_curriculum")
        self.assertEqual(
            split_evidence_families.__module__,
            "bilqis_mlx.factory.evidence_curriculum")
        self.assertEqual(
            tuple(inspect.signature(compile_evidence_lessons).parameters),
            ("adjudicated_snapshot", "source_rights", "semantic_release"),
        )
        with self.assertRaises(BilqisError):
            compile_evidence_lessons(
                self.snapshot, self.rights, "f" * 64)
        with self.assertRaises(BilqisError):
            compile_evidence_lessons(
                replace(self.snapshot, semantic_release="f" * 64),
                self.rights,
                "f" * 64,
            )

    def test_source_episode_identity_is_derived_not_caller_supplied(self):
        self.assertNotIn(
            "source_episode_ref",
            inspect.signature(parse_public_fixture_source).parameters,
        )
        self.assertNotIn("source_episode_ref", EvidenceRecord.__dataclass_fields__)

    def test_public_fixture_is_parsed_from_exact_source_bytes(self):
        record = parse_public_fixture_source(
            PUBLIC_FIXTURE_SOURCE,
            category_ref=STUDY, hour_unit_ref=HOUR, agent_role_ref=AGENT)
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
        result = self.compile()
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
        self.assertEqual(result.lessons[3].derivation.operator_id, "UNIT_CONVERT")
        self.assertEqual(result.lessons[3].derivation.input_unit_ref, HOUR)
        self.assertEqual(result.lessons[3].derivation.output_unit, "min")
        self.assertTrue(all(lesson.check() for lesson in result.lessons))

    def test_accepted_v1_public_snapshot_manifest_identity_still_compiles(self):
        legacy = replace(
            self.snapshot,
            source_manifest_cid=LEGACY_PUBLIC_FIXTURE_MANIFEST_CID,
        )
        result = compile_evidence_lessons(legacy, self.rights, RELEASE)
        self.assertEqual(result.holds, ())
        self.assertEqual(tuple(lesson.gold for lesson in result.lessons),
                         (STUDY, "COMPLETED", "0.25", "15"))
        self.assertTrue(all(lesson.check() for lesson in result.lessons))

    def test_exact_checker_rejects_correlated_generator_corruption(self):
        result = self.compile()
        minutes = result.lessons[3]
        self.assertFalse(replace(
            minutes,
            gold="14",
            derivation=replace(minutes.derivation, output_value="14"),
        ).check())
        self.assertFalse(replace(
            result.lessons[1],
            gold="FORGED",
            frame=replace(result.lessons[1].frame, status="FORGED"),
        ).check())
        self.assertFalse(replace(
            result.lessons[0],
            frame=replace(result.lessons[0].frame, actor_role_ref="forged-role"),
        ).check())

        precise = "0.12345678901234567890123456789"
        record = replace(
            self.snapshot.records[0],
            reported_value=ReportedValue(precise, HOUR),
        )
        precise_result = self.compile(replace(self.snapshot, records=(record,)))
        precise_minutes = precise_result.lessons[3]
        self.assertEqual(
            precise_minutes.gold,
            "7.4074073407407407340740740734",
        )
        self.assertTrue(precise_minutes.check())
        self.assertFalse(replace(
            precise_minutes,
            gold="7.407407340740740734074074073",
            derivation=replace(
                precise_minutes.derivation,
                output_value="7.407407340740740734074074073",
            ),
        ).check())

    def test_exact_hour_conversion_preserves_trailing_zero_magnitude(self):
        record = replace(
            self.snapshot.records[0], reported_value=ReportedValue("1", HOUR))
        result = self.compile(replace(self.snapshot, records=(record,)))
        self.assertEqual(result.lessons[3].gold, "60")
        self.assertTrue(result.lessons[3].check())

    def test_non_hour_report_does_not_mint_hour_to_minute_gold(self):
        record = replace(
            self.snapshot.records[0],
            reported_value=ReportedValue("15", "min"),
            unit_label="min",
        )
        with self.assertRaises(BilqisError) as caught:
            self.compile(replace(self.snapshot, records=(record,)))
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_EVIDENCE_DURATION_UNIT_UNQUALIFIED",
        )

    def test_planned_and_unknown_duration_are_distinct_from_completed_and_zero(self):
        record = self.snapshot.records[0]
        planned = replace(record, status="PLANNED")
        planned_snapshot = replace(self.snapshot, records=(planned,))
        planned_result = self.compile(planned_snapshot)
        self.assertEqual(planned_result.lessons[0].rendered, "actor_01 plans study for 0.25 h.")
        self.assertEqual(planned_result.lessons[1].gold, "PLANNED")
        self.assertEqual(planned_result.lessons[0].frame.occurrence_truth, "UNKNOWN")

        unknown = replace(record, reported_value=ReportedValue(None, HOUR))
        unknown_result = self.compile(replace(self.snapshot, records=(unknown,)))
        self.assertEqual(
            unknown_result.lessons[0].rendered,
            "actor_01 reported study; duration is unknown.",
        )
        self.assertEqual(unknown_result.lessons[2].gold, "UNKNOWN")
        self.assertEqual(unknown_result.lessons[3].gold, "UNKNOWN")

        zero = replace(record, reported_value=ReportedValue("0", HOUR))
        zero_result = self.compile(replace(self.snapshot, records=(zero,)))
        self.assertEqual(zero_result.lessons[2].gold, "0")
        self.assertEqual(zero_result.lessons[3].gold, "0")


if __name__ == "__main__":
    unittest.main()
