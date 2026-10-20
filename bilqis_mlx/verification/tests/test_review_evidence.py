"""Admission evidence must survive independent artifact and scope checks."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.next_grade_review import QUESTION_IDS, assess, load_review, subject_digest
from bilqis_mlx.verification.review_evidence import EvidenceContext
from bilqis_mlx.factory.tests.test_next_grade_review import evidence_fixture, proposal


class ReviewEvidenceTests(unittest.TestCase):
    def test_changed_verification_code_invalidates_unchanged_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = proposal()
            context = evidence_fixture(record, tmp)
            with patch("bilqis_mlx.verification.review_evidence.verifier_digest",
                       return_value="0" * 64, create=True):
                result = self.check(record, context)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("REVIEW_EVIDENCE_VERIFIER_DRIFT", result["blockers"])

    def test_pinned_manifest_without_checker_binding_is_insufficient(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = proposal()
            context = evidence_fixture(record, tmp)
            context = self.repin(context, lambda data: data.pop("verifier_sha256", None))
            self.assertIn("REVIEW_EVIDENCE_VERIFIER_DRIFT", self.check(record, context)["blockers"])

    def check(self, record, context, phase="admission"):
        return assess(record, grade=record["grade"], parent_release=record["parent_release"],
                      phase=phase, evidence=context)

    def repin(self, context, mutate):
        data = json.loads(context.manifest.read_text())
        mutate(data)
        context.manifest.write_text(json.dumps(data))
        return EvidenceContext(context.manifest, hashlib.sha256(context.manifest.read_bytes()).hexdigest(),
                               context.artifact_root)

    def test_evidence_shaped_strings_cannot_qualify_a_grade(self):
        result = assess(proposal(), grade="D", parent_release="fixed-parent-v1",
                        phase="admission")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("REVIEW_EVIDENCE_TRUST_ROOT_MISSING", result["blockers"])

    def test_dossier_cannot_supply_its_own_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "D.json").write_text(json.dumps(proposal()))
            result = load_review("D", Path(tmp))
            self.assertEqual(result["status"], "BLOCKED")
            self.assertIn("NEXT_GRADE_REVIEW_PARENT_REQUIRED", result["blockers"])

    def test_retrospective_outcome_does_not_rewrite_prior_phase_scope(self):
        record = proposal()
        before = subject_digest(record)
        record["run_outcome"] = {"retention": "NOT_MEASURED"}
        self.assertEqual(before, subject_digest(record))

    def test_malformed_json_root_is_a_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "D.json").write_text("[]")
            result = load_review("D", Path(tmp), parent_release="fixed-parent-v1")
            self.assertEqual(result["status"], "BLOCKED")

    def test_unhashable_alternative_never_crashes(self):
        record = copy.deepcopy(proposal())
        record["selected"] = ["unhashable"]
        result = assess(record, grade="D", parent_release="fixed-parent-v1")
        self.assertEqual(result["status"], "BLOCKED")

    def test_independently_pinned_exact_claims_reach_review_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = proposal()
            context = evidence_fixture(record, tmp)
            result = self.check(record, context)
            self.assertEqual(result["status"], "READY_FOR_INDEPENDENT_REVIEW")
            self.assertFalse(result["training_authorized_by_this_report"])

    def test_source_mutation_invalidates_unchanged_dossier(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = proposal()
            context = evidence_fixture(record, tmp)
            before = copy.deepcopy(record)
            Path(tmp, "witness.json").write_text('{"synthetic_independent_fixture":false}')
            result = self.check(record, context)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertTrue(any(b.startswith("REVIEW_EVIDENCE_ARTIFACT_DRIFT:") for b in result["blockers"]))
            self.assertEqual(record, before)

    def test_manifest_cannot_choose_its_own_expected_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = proposal()
            context = evidence_fixture(record, tmp)
            context.manifest.write_text(context.manifest.read_text() + " ")
            self.assertIn("REVIEW_EVIDENCE_MANIFEST_DRIFT", self.check(record, context)["blockers"])

    def test_new_independent_evidence_requires_new_dependent_phase_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = proposal()
            context = evidence_fixture(record, tmp)
            context = self.repin(context, lambda d: d["receipts"][0].update(reviewer="new-reviewer"))
            result = self.check(record, context)
            self.assertIn("REVIEW_EVIDENCE_SCOPE_STALE:selection", result["blockers"])

    def test_missing_artifact_and_path_escape_are_precise_debt(self):
        for path, code in (("missing.json", "ARTIFACT_MISSING"), ("../outside", "UNSAFE_PATH")):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as tmp:
                record = proposal()
                context = evidence_fixture(record, tmp)
                context = self.repin(context, lambda d: d["receipts"][0]["artifacts"][0].update(path=path))
                result = self.check(record, context)
                self.assertTrue(any(b.startswith("REVIEW_EVIDENCE_" + code + ":") for b in result["blockers"]))

    def test_symlink_artifact_cannot_escape_the_review_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = proposal()
            context = evidence_fixture(record, tmp)
            Path(tmp, "link.json").symlink_to(Path(tmp, "witness.json"))
            context = self.repin(context, lambda d: d["receipts"][0]["artifacts"][0].update(path="link.json"))
            self.assertTrue(any(b.startswith("REVIEW_EVIDENCE_UNSAFE_PATH:")
                                for b in self.check(record, context)["blockers"]))

    def test_a_receipt_for_one_question_does_not_qualify_another(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = proposal()
            context = evidence_fixture(record, tmp)
            record["reviews"]["selection"]["Q02"]["evidence"] = record["reviews"]["selection"]["Q01"]["evidence"]
            result = self.check(record, context)
            self.assertIn("REVIEW_QUESTION_UNRESOLVED:selection:Q02", result["blockers"])

    def test_self_qualification_and_stale_parent_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = proposal()
            context = evidence_fixture(record, tmp)
            context = self.repin(context, lambda d: d["receipts"][0].update(reviewer="fixture-author"))
            self.assertTrue(any(b.startswith("REVIEW_EVIDENCE_UNQUALIFIED:") for b in self.check(record, context)["blockers"]))
            context = self.repin(context, lambda d: d.update(parent_release="different-parent"))
            self.assertIn("REVIEW_EVIDENCE_SCOPE_MISMATCH:parent_release", self.check(record, context)["blockers"])

    def test_later_outcome_does_not_invalidate_earlier_phase_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = proposal()
            context = evidence_fixture(record, tmp)
            original = copy.deepcopy(record["reviews"])
            record["run_outcome"] = {"evidence": "receipt:outcome", "retention": "NOT_MEASURED"}
            for phase in ("operation", "retrospective"):
                record["reviews"][phase] = {q: {"status": "EVIDENCED", "evidence": [f"receipt:{phase}:{q}"]}
                                             for q in QUESTION_IDS}
                record["reviews"][phase]["subject_sha256"] = subject_digest(record, phase)
            # The reviewer issues a successor manifest with the additional phase claims.
            successor = evidence_fixture(record, tmp)
            record["reviews"].update(original)
            result = self.check(record, successor, phase="admission")
            self.assertEqual(result["status"], "READY_FOR_INDEPENDENT_REVIEW")

    def test_future_multiletter_grade_uses_the_same_review_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = proposal()
            record["grade"] = "AA"
            for phase in record["reviews"].values():
                phase["subject_sha256"] = subject_digest(record)
            context = evidence_fixture(record, tmp)
            self.assertEqual(self.check(record, context)["status"], "READY_FOR_INDEPENDENT_REVIEW")

    def test_alternatives_need_sources_for_a_credible_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = proposal()
            record["candidates"][1]["source"] = ""
            for phase in record["reviews"].values():
                phase["subject_sha256"] = subject_digest(record)
            context = evidence_fixture(record, tmp)
            result = self.check(record, context)
            self.assertIn("GRADE_CANDIDATE_SOURCE_UNVERIFIED:phonology", result["blockers"])

    def test_prerequisite_identity_is_typed_and_unique(self):
        for identity in (["bad"], {"bad": "id"}, ""):
            with self.subTest(identity=identity), tempfile.TemporaryDirectory() as tmp:
                record = proposal()
                record["candidates"][0]["prerequisites"][0]["id"] = identity
                for phase in record["reviews"].values():
                    phase["subject_sha256"] = subject_digest(record)
                context = evidence_fixture(record, tmp)
                self.assertIn("PREREQUISITE_IDENTITY_INVALID", self.check(record, context)["blockers"])
        with tempfile.TemporaryDirectory() as tmp:
            record = proposal()
            record["candidates"][0]["prerequisites"] *= 2
            context = evidence_fixture(record, tmp)
            self.assertIn("PREREQUISITE_IDENTITY_INVALID", self.check(record, context)["blockers"])
