from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.evidence_curriculum import (
    compile_evidence_lessons, split_evidence_families,
)
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.source_adapters.bravo.fixture import (
    compile_public_bravo_fixture_receipt,
    verify_public_bravo_fixture_receipt,
)
from bilqis_mlx.source_adapters.bravo.receipt import (
    EXPECTED_QUESTIONS, EXPECTED_RENDERED,
)
from bilqis_mlx.source_adapters.evidence_frames import (
    PUBLIC_FIXTURE_SOURCE, EvidenceSemanticAuthority, SourceSpan,
    build_public_fixture_snapshot,
)


RELEASE = "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306"
STUDY = (
    "https://github.com/Entif-AI/Bilqis-MLX/id/sense/"
    "NI-LEXICON-CURRICULUM/LEXROOT-3e51e33b4a970f/STEM%203/BSC")
HOUR = "h"
AGENT = "agent"
GRANT = "059ccd2a33330473973914b94fc0d772d6f845b6ee9c8e736f1876e6a9823e9f"


class PublicBravoFixtureTests(unittest.TestCase):
    def setUp(self):
        self.selection = AtlasArtifactSelection(
            "synthetic:test-atlas", "b" * 64, RELEASE, "c" * 64)
        authority = EvidenceSemanticAuthority(
            RELEASE, STUDY, HOUR, AGENT, "UNIT_CONVERT", GRANT)
        self._authority = patch(
            "bilqis_mlx.source_adapters.evidence_frames."
            "resolve_public_fixture_authority",
            return_value=authority)
        self._authority.start()
        self.addCleanup(self._authority.stop)

    def receipt(self):
        return compile_public_bravo_fixture_receipt(
            atlas_selection=self.selection)

    def test_literal_receipt_binds_replayable_source_and_all_four_golds(self):
        receipt = self.receipt()
        self.assertEqual(receipt.source_text, PUBLIC_FIXTURE_SOURCE)
        self.assertEqual(receipt.record_id, "fixture-001")
        self.assertEqual(receipt.actor_ref, "actor_01")
        self.assertEqual(receipt.category_ref, STUDY)
        self.assertEqual(receipt.agent_role_ref, AGENT)
        self.assertEqual(receipt.reported_unit_ref, HOUR)
        self.assertEqual(receipt.rendered, EXPECTED_RENDERED)
        self.assertEqual(
            tuple(row.question for row in receipt.witnesses),
            EXPECTED_QUESTIONS)
        self.assertEqual(
            tuple(row.gold for row in receipt.witnesses),
            (STUDY, "COMPLETED", "0.25", "15"))
        self.assertTrue(all(row.source_manifest_cid for row in receipt.witnesses))
        self.assertTrue(all(row.witness_sha256 for row in receipt.witnesses))
        self.assertIs(
            verify_public_bravo_fixture_receipt(
                receipt, atlas_selection=self.selection),
            receipt)

    def test_heldout_episode_has_four_independently_replayable_golds(self):
        receipt = self.receipt()
        split = receipt.f10_proof.independent_split
        self.assertNotEqual(split.train_family_id, split.heldout_family_id)
        self.assertNotEqual(split.train_source_digest, split.heldout_source_digest)
        self.assertEqual(
            tuple(row.question for row in split.heldout_witnesses),
            EXPECTED_QUESTIONS)
        self.assertEqual(
            tuple(row.gold for row in split.heldout_witnesses),
            (STUDY, "COMPLETED", "0.50", "30"))
        self.assertEqual(
            {row.source_family_id for row in split.heldout_witnesses},
            {split.heldout_family_id})
        self.assertEqual(
            {row.source_manifest_cid for row in split.heldout_witnesses},
            {split.heldout_source_manifest_cid})
        self.assertEqual(
            {row.rights for row in split.heldout_witnesses},
            {split.heldout_rights})
        self.assertEqual(
            split.heldout_rights,
            receipt.rights)

    def test_self_consistently_rehashed_tampering_fails_replay(self):
        receipt = self.receipt()
        changed = replace(receipt.witnesses[0], gold="FORGED")
        tampered = replace(
            receipt, witnesses=(changed, *receipt.witnesses[1:]))
        self.assertNotEqual(tampered.receipt_sha256, receipt.receipt_sha256)
        self.assertRegex(tampered.receipt_sha256, r"^[0-9a-f]{64}$")
        with self.assertRaises(BilqisError):
            verify_public_bravo_fixture_receipt(
                tampered, atlas_selection=self.selection)

    def test_manifest_family_or_source_tampering_fails_replay(self):
        receipt = self.receipt()
        with self.assertRaises(BilqisError):
            replace(receipt.witnesses[0], checker_id="forged-checker")
        for changed in (
            replace(receipt.witnesses[0], lesson_id="forged-lesson"),
            replace(receipt.witnesses[0], source_family_id="evidence-family:forged"),
            replace(receipt.witnesses[0], source_span_end=receipt.witnesses[0].source_span_end - 1),
            replace(
                receipt.witnesses[0],
                rights=replace(receipt.witnesses[0].rights, purpose="FORGED_PURPOSE")),
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(BilqisError):
                    tampered = replace(
                        receipt, witnesses=(changed, *receipt.witnesses[1:]))
                    verify_public_bravo_fixture_receipt(
                        tampered, atlas_selection=self.selection)

    def test_heldout_rights_purpose_tampering_fails_replay(self):
        receipt = self.receipt()
        split = receipt.f10_proof.independent_split
        forged_rights = replace(split.heldout_rights, purpose="FORGED_PURPOSE")
        forged_witnesses = tuple(
            replace(row, rights=forged_rights)
            for row in split.heldout_witnesses)
        tampered_split = replace(
            split,
            heldout_rights=forged_rights,
            heldout_witnesses=forged_witnesses)
        tampered = replace(
            receipt,
            f10_proof=replace(
                receipt.f10_proof, independent_split=tampered_split))
        with self.assertRaises(BilqisError):
            verify_public_bravo_fixture_receipt(
                tampered, atlas_selection=self.selection)

    def test_fixture_receipt_is_reproducible_and_source_digest_is_literal(self):
        first = self.receipt()
        second = self.receipt()
        self.assertEqual(first, second)
        self.assertEqual(
            first.source_byte_digest,
            sha256(PUBLIC_FIXTURE_SOURCE.encode("utf-8")).hexdigest())
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)

    def test_paraphrase_or_duplicate_cannot_create_an_independent_witness(self):
        snapshot, rights = build_public_fixture_snapshot(
            atlas_selection=self.selection)
        original = snapshot.records[0]
        paraphrase = replace(
            original,
            record_id="fixture-001-paraphrase",
            adjudication_ref="adjudication:renamed-does-not-create-evidence",
            source_span=SourceSpan(0, len(PUBLIC_FIXTURE_SOURCE)),
        )
        candidates = compile_evidence_lessons(
            replace(snapshot, records=(original, paraphrase)),
            rights,
            RELEASE,
        )
        with self.assertRaises(BilqisError):
            split_evidence_families(
                candidates,
                train_record_ids=(original.record_id,),
                heldout_record_ids=(paraphrase.record_id,),
            )

    def test_f10_receipt_records_duplicate_rejection_and_distinct_source(self):
        receipt = self.receipt()
        self.assertEqual(
            receipt.f10_proof.same_family_rejection_reason,
            "BAMF_EVIDENCE_SPLIT_WITNESS_NOT_INDEPENDENT")
        split = receipt.f10_proof.independent_split
        self.assertNotEqual(split.train_family_id, split.heldout_family_id)
        self.assertNotEqual(
            split.train_source_manifest_cid, split.heldout_source_manifest_cid)


@unittest.skipUnless(
    os.environ.get("BILQIS_A01_ATLAS_BUNDLE"),
    "real pinned A01 artifact is an optional integration witness",
)
class PublicBravoRealAuthorityTests(unittest.TestCase):
    def test_real_pinned_a01_a03_and_operator_authority_replay_receipt(self):
        root = Path(__file__).resolve().parents[3]
        pin = json.loads(
            (root / "bilqis_mlx/semantics/atlas_source_pins_v1.json").read_text()
        )["entries"][0]
        selection = AtlasArtifactSelection(
            os.environ["BILQIS_A01_ATLAS_BUNDLE"],
            pin["bundle_id"],
            pin["release_sha256"],
            pin["source_bundle_id"],
        )
        receipt = compile_public_bravo_fixture_receipt(
            atlas_selection=selection)
        self.assertEqual(receipt.semantic_release, pin["release_sha256"])
        self.assertEqual(receipt.category_ref, STUDY)
        self.assertIs(
            verify_public_bravo_fixture_receipt(
                receipt, atlas_selection=selection),
            receipt)


if __name__ == "__main__":
    unittest.main()
