import unittest

from bilqis_mlx.errors import BilqisError, SCHOOL
from bilqis_mlx.runtime.delivery import (
    BamfDeliveryManifest, CommitReceipt, ComponentReceipt, EgmReceipt, EgmStatus,
    IssueReceipt, OperatorCommandReceipt, ProofReceipt, ProofState, ReceiptStatus,
    integrate_delivery_receipts,
)


SHA = "a" * 40


def manifest():
    return BamfDeliveryManifest(
        components=(ComponentReceipt("C13", 385, SHA, ReceiptStatus.PROVISIONAL,
                                     "issue:385#checkpoint"),),
        issues=(IssueReceipt(385, "C13", "OPEN", ReceiptStatus.PROVISIONAL, SHA,
                             "issue:385"),),
        commits=(CommitReceipt(SHA, 385, "current development receipt"),),
        proofs=(ProofReceipt("C13.current", ProofState.EXECUTED_PASS,
                             "bilqis.c13.input/v1", "bilqis.c13.receipt/v1",
                             "issue:528#checkpoint", "16/16 PASS"),),
        egm=(EgmReceipt("codebase-details", EgmStatus.PENDING, SHA,
                        "EGM_PENDING:C15.1a"),),
        operator_commands=(OperatorCommandReceipt(
            "owner-resume", ("npm", "run", "train", "--", "--human-run", "--resume"),
            ProofState.EXECUTED_PASS, "test_bamf_resume.py", "docs:runbook"),),
    )


class DeliveryContractTests(unittest.TestCase):
    def test_manifest_is_deterministic_and_keeps_open_dependency_provisional(self):
        value = manifest()
        self.assertEqual(value.digest(), manifest().digest())
        self.assertEqual(value.issues[0].state, "OPEN")
        self.assertIs(value.issues[0].status, ReceiptStatus.PROVISIONAL)
        self.assertEqual(value.software_delivery_status, "IN_PROGRESS")
        self.assertEqual(value.student_mastery_status, "NOT_CLAIMED")

    def test_manifest_rejects_duplicate_or_noncanonical_receipts(self):
        value = manifest()
        with self.assertRaises(BilqisError) as caught:
            BamfDeliveryManifest(value.components, value.issues,
                                 value.commits + value.commits, value.proofs,
                                 value.egm, value.operator_commands)
        self.assertIs(caught.exception.spec, SCHOOL.BAMF_DELIVERY.INVALID)

    def test_command_receipt_requires_nonempty_argv(self):
        with self.assertRaises(BilqisError) as caught:
            OperatorCommandReceipt("resume", (), ProofState.CODE_PRESENT,
                                   "test_bamf_resume.py", "docs:runbook")
        self.assertIs(caught.exception.spec, SCHOOL.BAMF_DELIVERY.INVALID)


if __name__ == "__main__":
    unittest.main()
