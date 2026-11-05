from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.evidence_curriculum import (
    compile_evidence_lessons,
    split_evidence_families,
)
from bilqis_mlx.source_adapters.evidence_frames import (
    PUBLIC_FIXTURE_SOURCE,
    EvidenceSemanticAuthority,
    SourceSpan,
    build_public_fixture_snapshot,
)
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.source_adapters.bravo.fixture import (
    EXPECTED_QUESTIONS,
    EXPECTED_RENDERED,
    compile_public_bravo_fixture_receipt,
)


RELEASE = "58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306"
STUDY = (
    "https://github.com/Entif-AI/Bilqis-MLX/id/sense/"
    "NI-LEXICON-CURRICULUM/LEXROOT-3e51e33b4a970f/STEM%203/BSC"
)
HOUR = "h"
AGENT = "agent"


class PublicBravoFixtureTests(unittest.TestCase):
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

    def receipt(self):
        return compile_public_bravo_fixture_receipt(
            atlas_selection=self.selection,
        )

    def test_literal_fixture_receipt_binds_exact_source_record_frame_lessons_and_checkers(self):
        receipt = self.receipt()
        self.assertEqual(receipt.source_text, PUBLIC_FIXTURE_SOURCE)
        self.assertEqual(receipt.record_id, "fixture-001")
        self.assertEqual(receipt.actor_ref, "actor_01")
        self.assertEqual(receipt.category_ref, STUDY)
        self.assertEqual(receipt.agent_role_ref, AGENT)
        self.assertEqual(receipt.reported_unit_ref, HOUR)
        self.assertEqual(receipt.rendered, EXPECTED_RENDERED)
        self.assertEqual(tuple(row.question for row in receipt.witnesses), EXPECTED_QUESTIONS)
        self.assertEqual(tuple(row.gold for row in receipt.witnesses), (STUDY, "COMPLETED", "0.25", "15"))
        self.assertTrue(all(row.checker_passed for row in receipt.witnesses))
        self.assertTrue(all(
            row.checker_id == "bilqis.evidence-exact-checker/v1"
            for row in receipt.witnesses))
        self.assertEqual(
            {row.external_witness_ref for row in receipt.witnesses},
            {"adjudication:fixture-001"},
        )
        self.assertEqual(len({row.source_binding_sha256 for row in receipt.witnesses}), 4)

    def test_every_derivative_retains_family_rights_and_interpretation_lineage(self):
        receipt = self.receipt()
        self.assertEqual(len({row.source_family_id for row in receipt.witnesses}), 1)
        self.assertEqual(
            {row.source_family_id for row in receipt.witnesses},
            {receipt.source_family_id},
        )
        self.assertEqual(
            {row.interpretation_revision for row in receipt.witnesses},
            {receipt.interpretation_revision},
        )
        self.assertEqual({row.rights_regime for row in receipt.witnesses}, {"PUBLIC_FIXTURE"})

    def test_fixture_receipt_is_reproducible_and_source_digest_is_literal(self):
        first = self.receipt()
        second = self.receipt()
        self.assertEqual(first, second)
        self.assertEqual(
            first.source_byte_digest,
            sha256(PUBLIC_FIXTURE_SOURCE.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)

    def test_receipt_hash_binds_frame_witness_and_split_material(self):
        receipt = self.receipt()
        baseline = receipt.receipt_sha256

        changed_frame = replace(receipt, category_ref="tampered-category")
        self.assertNotEqual(changed_frame.receipt_sha256, baseline)

        changed_witness = replace(receipt.witnesses[0], gold="tampered-gold")
        witness_receipt = replace(
            receipt,
            witnesses=(changed_witness, *receipt.witnesses[1:]),
        )
        self.assertNotEqual(witness_receipt.receipt_sha256, baseline)

        changed_external_split = replace(
            receipt.f10_proof.independent_split,
            heldout_external_witness_ref="adjudication:tampered",
        )
        split_receipt = replace(
            receipt,
            f10_proof=replace(
                receipt.f10_proof,
                independent_split=changed_external_split,
            ),
        )
        self.assertNotEqual(split_receipt.receipt_sha256, baseline)

    def test_paraphrase_or_duplicate_cannot_create_an_independent_witness(self):
        snapshot, rights = build_public_fixture_snapshot(
            atlas_selection=self.selection,
        )
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

    def test_f10_receipt_records_rejected_duplicate_and_distinct_external_source(self):
        receipt = self.receipt()
        self.assertEqual(
            receipt.f10_proof.same_family_rejection_reason,
            "BAMF_EVIDENCE_SPLIT_WITNESS_NOT_INDEPENDENT",
        )
        split = receipt.f10_proof.independent_split
        self.assertNotEqual(split.train_family_id, split.heldout_family_id)
        self.assertNotEqual(split.train_source_digest, split.heldout_source_digest)
        self.assertIn("independent", split.heldout_source_manifest_cid)


if __name__ == "__main__":
    unittest.main()
