"""Reusable A10.1 F10 and authority cases; mixed into the issue-owned suite."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import os
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.evidence_curriculum import (
    compile_evidence_lessons, plan_fresh_challenge, split_evidence_families,
)
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.source_adapters.evidence_frames import (
    PUBLIC_DUPLICATE_MANIFEST_CID, PUBLIC_DUPLICATE_SOURCE,
    PUBLIC_FIXTURE_REPACK_MANIFEST_CID, PUBLIC_FIXTURE_SOURCE,
    PUBLIC_INDEPENDENT_BUNDLE_SOURCE, PUBLIC_INDEPENDENT_MANIFEST_CID,
    PUBLIC_INDEPENDENT_SOURCE, ReportedValue, SourceSpan,
    build_public_fixture_snapshot, parse_public_fixture_source, source_family_id,
)


STUDY = (
    "https://github.com/Entif-AI/Bilqis-MLX/id/sense/"
    "NI-LEXICON-CURRICULUM/LEXROOT-3e51e33b4a970f/STEM%203/BSC"
)
HOUR = "h"
AGENT = "agent"
SOURCE_BUNDLE = "f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec"
ATLAS_BUNDLE = "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7"
ATLAS_RELEASE = "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306"
class EvidenceFamilyAuthorityCases:
    def _duplicate_source_snapshot(self, *, second_record_id):
        first = replace(
            self.snapshot.records[0],
            source_span=SourceSpan(0, len(PUBLIC_FIXTURE_SOURCE)),
        )
        second_start = len(PUBLIC_FIXTURE_SOURCE) + 1
        duplicate = replace(
            first, record_id=second_record_id,
            source_span=SourceSpan(
                second_start, second_start + len(PUBLIC_FIXTURE_SOURCE)),
            adjudication_ref=f"adjudication:{second_record_id}",
        )
        snapshot = replace(
            self.snapshot,
            source_manifest_cid=PUBLIC_DUPLICATE_MANIFEST_CID,
            source_byte_digest=sha256(
                PUBLIC_DUPLICATE_SOURCE.encode("utf-8")).hexdigest(),
            records=(first, duplicate),
        )
        return snapshot, first, duplicate

    def _independent_source_snapshot(self, *, second_record_id):
        first = replace(
            self.snapshot.records[0],
            source_span=SourceSpan(0, len(PUBLIC_FIXTURE_SOURCE)),
        )
        parsed = parse_public_fixture_source(
            PUBLIC_INDEPENDENT_SOURCE,
            category_ref=first.category_ref,
            hour_unit_ref=first.reported_value.unit_ref,
            agent_role_ref=first.agent_role_ref,
        )
        second_start = len(PUBLIC_FIXTURE_SOURCE) + 1
        separate = replace(
            parsed, record_id=second_record_id,
            source_span=SourceSpan(
                second_start, second_start + len(PUBLIC_INDEPENDENT_SOURCE)),
            adjudication_ref=f"adjudication:{second_record_id}",
        )
        snapshot = replace(
            self.snapshot,
            source_manifest_cid=PUBLIC_INDEPENDENT_MANIFEST_CID,
            source_byte_digest=sha256(
                PUBLIC_INDEPENDENT_BUNDLE_SOURCE.encode("utf-8")).hexdigest(),
            records=(first, separate),
        )
        return snapshot, first, separate

    def test_paraphrases_of_one_episode_cannot_cross_independent_split(self):
        original = self.snapshot.records[0]
        sibling = replace(original, record_id="fixture-001-paraphrase")
        result = self.compile(replace(self.snapshot, records=(original, sibling)))
        with self.assertRaises(ValueError):
            split_evidence_families(
                result, train_record_ids=(original.record_id,),
                heldout_record_ids=(sibling.record_id,))
        same_side = split_evidence_families(
            result, train_record_ids=(original.record_id, sibling.record_id),
            heldout_record_ids=())
        self.assertEqual(len(same_side.train_family_ids), 1)

        adjudicated_copy = replace(
            original, record_id="fixture-002",
            adjudication_ref="adjudication:fixture-002")
        copied = self.compile(
            replace(self.snapshot, records=(original, adjudicated_copy)))
        with self.assertRaises(ValueError):
            split_evidence_families(
                copied, train_record_ids=(original.record_id,),
                heldout_record_ids=(adjudicated_copy.record_id,))

        combined, first, separate = self._independent_source_snapshot(
            second_record_id="fixture-003")
        independent = self.compile(combined)
        receipt = split_evidence_families(
            independent, train_record_ids=(first.record_id,),
            heldout_record_ids=(separate.record_id,))
        self.assertNotEqual(receipt.train_family_ids, receipt.heldout_family_ids)

    def test_unregistered_source_manifest_cannot_mint_family_authority(self):
        forged = replace(
            self.snapshot,
            source_manifest_cid="public-fixture:caller-minted/v1:" + "f" * 64,
        )
        with self.assertRaises(BilqisError):
            source_family_id(forged, forged.records[0])

    def test_manifest_repacking_cannot_manufacture_new_episode_family(self):
        original = self.snapshot.records[0]
        copied = replace(original, record_id="fixture-copy")
        repacked = replace(
            self.snapshot, source_manifest_cid=PUBLIC_FIXTURE_REPACK_MANIFEST_CID,
            records=(copied,))
        self.assertEqual(
            source_family_id(self.snapshot, original),
            source_family_id(repacked, copied))

    def test_duplicate_source_at_second_span_cannot_manufacture_family(self):
        combined, original, duplicate = self._duplicate_source_snapshot(
            second_record_id="fixture-duplicate")
        self.assertEqual(
            source_family_id(combined, original),
            source_family_id(combined, duplicate),
        )

    def test_distinct_source_observation_occurrences_remain_independent(self):
        combined, original, separate = self._independent_source_snapshot(
            second_record_id="fixture-separate")
        result = self.compile(combined)
        receipt = split_evidence_families(
            result,
            train_record_ids=(original.record_id,),
            heldout_record_ids=(separate.record_id,),
        )
        self.assertNotEqual(
            receipt.train_family_ids, receipt.heldout_family_ids)

    def test_same_root_correction_cannot_manufacture_independent_family(self):
        original = self.snapshot.records[0]
        corrected = replace(
            original,
            record_id="fixture-corrected",
            status="PLANNED",
            adjudication_ref="adjudication:fixture-corrected",
        )
        result = self.compile(
            replace(self.snapshot, records=(original, corrected)))
        with self.assertRaises(ValueError):
            split_evidence_families(
                result,
                train_record_ids=(original.record_id,),
                heldout_record_ids=(corrected.record_id,),
            )

    def test_fresh_challenge_splits_source_families_before_template_groups(self):
        combined, original, other = self._independent_source_snapshot(
            second_record_id="fixture-002")
        paraphrase = replace(original, record_id="fixture-001-paraphrase")
        result = self.compile(replace(
            combined, records=(original, paraphrase, other)))
        with self.assertRaises(ValueError):
            plan_fresh_challenge(
                result, train_record_ids=(original.record_id,),
                heldout_record_ids=(paraphrase.record_id,))
        plan = plan_fresh_challenge(
            result,
            train_record_ids=(original.record_id, paraphrase.record_id),
            heldout_record_ids=(other.record_id,))
        self.assertEqual(len(plan.split.train_family_ids), 1)
        self.assertEqual(len(plan.split.heldout_family_ids), 1)
        self.assertEqual(plan.train_template_groups[0][1], "T1")
        self.assertEqual(plan.heldout_template_groups[0][1], "T1")
        self.assertEqual(
            set(plan.post_exam_teachable_lesson_ids),
            {lesson.lesson_id for lesson in result.lessons
             if lesson.record_id == other.record_id})

    def test_missing_report_is_verification_needed_not_nonoccurrence(self):
        record = replace(
            self.snapshot.records[0], status="PLANNED",
            reported_value=ReportedValue(None, HOUR),
            alternatives=("EXPECTED_REPORT_MISSING",))
        result = self.compile(replace(self.snapshot, records=(record,)))
        self.assertEqual(
            result.lessons[0].frame.verification_state, "VERIFICATION_NEEDED")
        self.assertNotIn("NON_OCCURRENCE", result.lessons[0].frame.alternatives)

    def test_compiler_reenters_semantic_authority_before_gold(self):
        record = self.snapshot.records[0]
        for forged, reason in (
            (replace(record, category_ref="fixture:invented-category"),
             "BAMF_EVIDENCE_COMPILER_AUTHORITY_MISMATCH"),
            (replace(record, agent_role_ref="fixture:invented-agent-role"),
             "BAMF_EVIDENCE_COMPILER_AUTHORITY_MISMATCH"),
            (replace(record, reported_value=ReportedValue("0.25", "invented-unit")),
             "BAMF_EVIDENCE_COMPILER_AUTHORITY_MISMATCH"),
            (replace(
                record,
                reported_value=ReportedValue("0.25", "min"),
                unit_label="h",
            ), "BAMF_EVIDENCE_DURATION_UNIT_UNQUALIFIED"),
            (replace(record, unit_label="min"),
             "BAMF_EVIDENCE_DURATION_UNIT_UNQUALIFIED"),
        ):
            with self.subTest(forged=forged):
                with self.assertRaises(BilqisError) as caught:
                    self.compile(replace(self.snapshot, records=(forged,)))
                self.assertEqual(caught.exception.context["reason"], reason)

    @unittest.skipUnless(
        os.environ.get("BILQIS_A01_ATLAS_BUNDLE"),
        "real pinned A01 artifact is an optional integration witness",
    )
    def test_real_pinned_a01_a03_and_unit_authority_build_fixture(self):
        self._source_authority.stop()
        self._compiler_authority.stop()
        selection = AtlasArtifactSelection(
            os.environ["BILQIS_A01_ATLAS_BUNDLE"],
            ATLAS_BUNDLE, ATLAS_RELEASE, SOURCE_BUNDLE)
        snapshot, rights = build_public_fixture_snapshot(
            atlas_selection=selection)
        result = compile_evidence_lessons(snapshot, rights, selection)
        self.assertEqual(snapshot.semantic_release, ATLAS_RELEASE)
        self.assertEqual(snapshot.records[0].category_ref, STUDY)
        self.assertEqual(snapshot.records[0].reported_value.unit_ref, HOUR)
        self.assertEqual(snapshot.records[0].agent_role_ref, AGENT)
        self.assertEqual(result.lessons[3].gold, "15")
        self.assertTrue(all(lesson.check() for lesson in result.lessons))
