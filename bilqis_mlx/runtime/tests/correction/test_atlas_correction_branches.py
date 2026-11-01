"""Source-authenticated correction branches behavior."""
import unittest

from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    BilqisError, CorrectionBranches, DependencyKind, DependencyRef,
    _event, _ref, _sign_event, add_correction,
    replace,
)


class CorrectionBranchesTests(unittest.TestCase):
    def test_concurrent_corrections_keep_branches_until_explicit_supersession(self):
        source = _ref(DependencyKind.SOURCE, "source:meeting")
        original = _event(source)
        alternative = _sign_event(replace(
            original, event_id="correction:synthetic:2",
            new_evidence_sha256="d" * 64,
            source_receipt_sha256="e" * 64))
        branches = add_correction(CorrectionBranches(source, ()), original)
        concurrent = add_correction(branches, alternative)
        self.assertEqual(
            tuple(item.event.event_id for item in concurrent.active),
            ("correction:synthetic:1", "correction:synthetic:2"))
        self.assertEqual(add_correction(concurrent, alternative), concurrent)
        with self.assertRaises(BilqisError) as caught:
            add_correction(concurrent, _sign_event(replace(
                original, new_evidence_sha256="0" * 64)))
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_CORRECTION_EVENT_ID_CONFLICT")
        superseding = _sign_event(replace(
            original, event_id="correction:synthetic:3",
            supersedes_event_ids=("correction:synthetic:1", "correction:synthetic:2"),
            new_evidence_sha256="9" * 64))
        resolved = add_correction(
            concurrent, superseding,
            supersedes_event_ids=("correction:synthetic:1",
                                  "correction:synthetic:2"))
        self.assertEqual(tuple(item.event.event_id for item in resolved.active),
                         ("correction:synthetic:3",))
        self.assertEqual(len(resolved.branches), 3)
        self.assertEqual(len(concurrent.branches), 2)

    def test_unsigned_supersession_cannot_retire_authenticated_alternatives(self):
        source = DependencyRef(DependencyKind.SOURCE, 'source:synthetic')
        original = _event(source)
        branches = add_correction(CorrectionBranches(source, ()), original)
        other = _sign_event(replace(original, event_id='correction:other'))
        with self.assertRaises(BilqisError):
            add_correction(branches, other, supersedes_event_ids=(original.event_id,))
        tampered = replace(other, supersedes_event_ids=(original.event_id,))
        with self.assertRaises(BilqisError) as caught:
            add_correction(branches, tampered, supersedes_event_ids=(original.event_id,))
        self.assertEqual(caught.exception.context['reason'], 'BAMF_C09_SOURCE_SIGNATURE_INVALID')
