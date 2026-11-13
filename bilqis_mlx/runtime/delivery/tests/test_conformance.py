import copy
import unittest

from bilqis_mlx.errors import BilqisError, SCHOOL
from bilqis_mlx.runtime.delivery import ProofState
from bilqis_mlx.runtime.delivery.conformance import (
    AuthorityIdentity, ConformanceProjection, ConformanceRow, EvidenceBinding,
    ExecutionReceipt, FailureGate, admitted_state, load_conformance_record,
    required_claim_ids,
)


SOURCE = b"authoritative workstack bytes"
CONTRACT = b"authoritative contract bytes"
ISSUE = b"authoritative issue bytes"
SHA = "a" * 40


def evidence(*, receipt=True, identity=None, reviewer="PASS"):
    fixture = "fixtures/literal.json"
    expected = "independent expected behavior"
    observed = "literal observed behavior"
    runner = "python3.14 unittest local-macos"
    run_receipt = (ExecutionReceipt.from_execution(
        candidate_sha=SHA, fixture=fixture, expected=expected, observed=observed,
        runner=runner, disposition="PASS") if receipt else None)
    return EvidenceBinding(
        "literal acceptance clause", "BAMF-0.2-SPEC-001@v0.2.0", 539, SHA,
        "docs/architecture/BAMF_0_2.md", fixture, expected, observed, runner,
        run_receipt, reviewer,
        identity or AuthorityIdentity.from_authorities(
            source=SOURCE, contract=CONTRACT, issue=ISSUE))


def rows(state=ProofState.SPECIFIED):
    return tuple(ConformanceRow(
        claim_id, "docs/tasks/bamf-0.2/ISSUE_BOOK.md",
        "docs/architecture/BAMF_0_2.md", f"tests/{claim_id}.py", state,
        evidence()) for claim_id in required_claim_ids())


def gates(state=ProofState.CODE_PRESENT):
    return (
        FailureGate("GRADE_NEUTRAL_INVARIANCE", "tests/grade_neutral.py",
                    state, "current-head witness"),
        FailureGate("NO_LEGACY_BAV_RUNTIME_NAMESPACE", "tests/no_bav.py",
                    state, "current-head witness"),
    )


class ConformanceProjectionTests(unittest.TestCase):
    def test_projection_requires_all_24_requirements_and_20_failures_in_order(self):
        value = ConformanceProjection(rows(), gates(), "IN_PROGRESS", "NOT_CLAIMED")
        self.assertEqual(len(value.rows), 44)
        self.assertEqual(value.rows[0].claim_id, "BAMF-REQ-001")
        self.assertEqual(value.rows[-1].claim_id, "F20")

    def test_executed_pass_requires_structured_fresh_receipt(self):
        with self.assertRaises(BilqisError) as caught:
            admitted_state(ProofState.EXECUTED_PASS, evidence(receipt=False),
                           source=SOURCE, contract=CONTRACT, issue=ISSUE)
        self.assertIs(caught.exception.spec, SCHOOL.BAMF_DELIVERY.INVALID)

    def test_failure_gate_precedes_green_evidence(self):
        self.assertIs(admitted_state(
            ProofState.EXECUTED_PASS, evidence(), source=SOURCE, contract=CONTRACT,
            issue=ISSUE, failure_gates=("GRADE_NEUTRAL_INVARIANCE_FAILED",)),
            ProofState.EXECUTED_FAIL)

    def test_authority_drift_requires_requalification(self):
        self.assertIs(admitted_state(
            ProofState.EXECUTED_PASS, evidence(), source=SOURCE,
            contract=CONTRACT + b" changed", issue=ISSUE),
            ProofState.REQUALIFICATION_REQUIRED)

    def test_malformed_authority_digest_is_rejected(self):
        with self.assertRaises(BilqisError):
            AuthorityIdentity("not-a-digest", "b" * 64, "c" * 64)

    def test_ready_refuses_code_present_rows(self):
        with self.assertRaises(BilqisError) as caught:
            ConformanceProjection(rows(), gates(), "READY_FOR_OWNER_MERGE", "NOT_CLAIMED")
        self.assertIs(caught.exception.spec, SCHOOL.BAMF_DELIVERY.INVALID)

    def test_all_executed_pass_rows_and_gates_can_reach_ready(self):
        value = ConformanceProjection(
            rows(ProofState.EXECUTED_PASS), gates(ProofState.EXECUTED_PASS),
            "READY_FOR_OWNER_MERGE", "NOT_CLAIMED")
        record = {**value.to_record(), "conformance_sha256": value.digest()}
        self.assertEqual(load_conformance_record(record), value)

    def test_failed_global_gate_forces_blocked_delivery(self):
        failed_gates = (
            FailureGate("GRADE_NEUTRAL_INVARIANCE", "tests/grade_neutral.py",
                        ProofState.EXECUTED_FAIL, "grade permutation changed selection"),
            gates()[1],
        )
        with self.assertRaises(BilqisError):
            ConformanceProjection(rows(), failed_gates, "IN_PROGRESS", "NOT_CLAIMED")

    def test_v1_or_legacy_shape_is_refused(self):
        value = ConformanceProjection(rows(), gates(), "IN_PROGRESS", "NOT_CLAIMED")
        record = {**value.to_record(), "conformance_sha256": value.digest()}
        legacy = copy.deepcopy(record)
        legacy["schema"] = "bilqis.bamf.delivery-conformance/v1"
        with self.assertRaises(BilqisError):
            load_conformance_record(legacy)
        missing = copy.deepcopy(record)
        del missing["rows"][0]["evidence"]["authority_identity"]
        with self.assertRaises(BilqisError):
            load_conformance_record(missing)


if __name__ == "__main__":
    unittest.main()
