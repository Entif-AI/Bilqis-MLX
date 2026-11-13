import unittest

from bilqis_mlx.errors import BilqisError, SCHOOL
from bilqis_mlx.runtime.delivery import (
    CommitReceipt, ComponentReceipt, EgmReceipt, EgmStatus, IssueReceipt,
    OperatorCommandReceipt, ProofReceipt, ProofState, ReceiptStatus,
    integrate_delivery_receipts,
)
from bilqis_mlx.runtime.delivery.tests.test_conformance import gates, rows
from bilqis_mlx.runtime.delivery.conformance import ConformanceProjection


SHA = "b" * 40
COMPONENTS = ("B14", "C11", "C12", "C13", "C14", "C16")
COMMANDS = ("cold-resume", "owner-start", "preflight", "read-only-status")


def component(name, status=ReceiptStatus.ACCEPTED):
    number = {"B14": 375, "C11": 384, "C12": 381,
              "C13": 385, "C14": 386, "C16": 382}[name]
    return ComponentReceipt(name, number, SHA, status, f"issue:{number}")


def command(name, state=ProofState.EXECUTED_PASS):
    return OperatorCommandReceipt(
        name, ("npm", "run", "train", "--", "--help"), state,
        "test_operator_parser.py", "docs:runbook")


def conformance():
    return ConformanceProjection(rows(), gates(), "IN_PROGRESS", "NOT_CLAIMED")


def integrate(components, egm_status=EgmStatus.PASS, *,
              command_state=ProofState.EXECUTED_PASS, conformance_value=None):
    dependency_components = tuple(item for item in components
                                  if item.component_id in COMPONENTS)
    issues = tuple(sorted(
        (IssueReceipt(item.owner_issue, item.component_id, "CLOSED",
                      item.status, item.head_sha, item.evidence_ref)
         for item in dependency_components), key=lambda item: item.issue))
    commits = tuple(CommitReceipt(item.head_sha[:-1] + str(index), item.owner_issue,
                                  "delivery owner")
                    for index, item in enumerate(dependency_components))
    proofs = (ProofReceipt("workstack", ProofState.EXECUTED_PASS,
                           "bilqis.bamf.workstack/v1",
                           "bilqis.bamf.workstack.validation/v1",
                           "scripts/check_bamf_workstack.py", "held_keys=[]"),)
    egm = tuple(EgmReceipt(name, egm_status, SHA, "report:egm")
                for name in ("codebase-details", "implementation-readiness"))
    commands = tuple(command(name, command_state) for name in COMMANDS)
    return integrate_delivery_receipts(
        components=components, issues=issues, commits=commits, proofs=proofs,
        egm=egm, operator_commands=commands,
        conformance=conformance_value or conformance())


class DeliveryIntegrationTests(unittest.TestCase):
    def test_pending_upstream_receipt_stays_in_progress_without_mastery_claim(self):
        components = tuple(component(name, ReceiptStatus.PROVISIONAL
                                     if name in {"C13", "C14"}
                                     else ReceiptStatus.ACCEPTED)
                           for name in COMPONENTS)
        value = integrate(components, EgmStatus.PENDING)
        self.assertEqual(value.software_delivery_status, "IN_PROGRESS")
        self.assertEqual(value.student_mastery_status, "NOT_CLAIMED")

    def test_receipts_cannot_reach_ready_without_conformance_closure(self):
        value = integrate(tuple(component(name) for name in COMPONENTS))
        self.assertEqual(value.software_delivery_status, "IN_PROGRESS")

    def test_duck_typed_ready_conformance_is_rejected(self):
        class FakeReady:
            software_delivery_status = "READY_FOR_OWNER_MERGE"
            student_mastery_status = "NOT_CLAIMED"
        with self.assertRaises(BilqisError):
            integrate(tuple(component(name) for name in COMPONENTS),
                      conformance_value=FakeReady())

    def test_additional_component_pins_do_not_replace_required_dependencies(self):
        components = tuple(sorted(
            (*tuple(component(name) for name in COMPONENTS),
             ComponentReceipt("topology", 382, "c" * 64, ReceiptStatus.ACCEPTED,
                              "configs/models/bamf-0.2.json")),
            key=lambda item: item.component_id))
        value = integrate(components)
        self.assertIn("topology", {item.component_id for item in value.components})

    def test_code_present_operator_command_cannot_integrate(self):
        with self.assertRaises(BilqisError):
            integrate(tuple(component(name) for name in COMPONENTS),
                      command_state=ProofState.CODE_PRESENT)

    def test_missing_required_component_refuses_integration(self):
        with self.assertRaises(BilqisError) as caught:
            integrate(tuple(component(name) for name in COMPONENTS[:-1]))
        self.assertIs(caught.exception.spec, SCHOOL.BAMF_DELIVERY.INVALID)


if __name__ == "__main__":
    unittest.main()
