import unittest

from bilqis_mlx.errors import BilqisError, SCHOOL
from bilqis_mlx.runtime.delivery import ProofState
from bilqis_mlx.runtime.delivery.conformance import (
    ConformanceProjection, ConformanceRow, EvidenceBinding, FailureGate, admitted_state,
    required_claim_ids,
)


def evidence(**changes):
    values = {
        "normative_text": "literal acceptance clause",
        "variant_revision": "BAMF-0.2-SPEC-001@v0.2.0",
        "owner_issue": 539,
        "owner_commit": "a" * 40,
        "contract_path": "docs/architecture/BAMF_0_2.md",
        "input_fixture": "fixtures/literal.json",
        "expected_behavior": "literal independent expectation",
        "observed_output": "PASS literal observed behavior",
        "runner_environment": "python3.14 unittest local-macos",
        "fresh_run_receipt": "receipt:c15-2:001",
        "reviewer_decision": "PASS",
        "source_digest": "b" * 64,
        "contract_digest": "c" * 64,
        "issue_digest": "d" * 64,
    }
    values.update(changes)
    return EvidenceBinding(**values)


def rows():
    return tuple(ConformanceRow(
        claim_id, "docs/tasks/bamf-0.2/ISSUE_BOOK.md",
        "docs/architecture/BAMF_0_2.md", f"tests/{claim_id}.py", ProofState.SPECIFIED,
        evidence())
        for claim_id in required_claim_ids())


def gates():
    return (
        FailureGate("GRADE_NEUTRAL_INVARIANCE", "tests/grade_neutral.py",
                    ProofState.CODE_PRESENT, "current-head rerun pending"),
        FailureGate("NO_LEGACY_BAV_RUNTIME_NAMESPACE", "tests/no_bav.py",
                    ProofState.CODE_PRESENT, "current-head rerun pending"),
    )


class ConformanceProjectionTests(unittest.TestCase):
    def test_projection_requires_all_24_requirements_and_20_failures_in_order(self):
        value = ConformanceProjection(rows(), gates(), "IN_PROGRESS", "NOT_CLAIMED")
        self.assertEqual(len(value.rows), 44)
        self.assertEqual(value.rows[0].claim_id, "BAMF-REQ-001")
        self.assertEqual(value.rows[-1].claim_id, "F20")
        self.assertEqual(value.digest(), ConformanceProjection(
            rows(), gates(), "IN_PROGRESS", "NOT_CLAIMED").digest())

    def test_projection_refuses_missing_row_and_keeps_mastery_separate(self):
        with self.assertRaises(BilqisError) as caught:
            ConformanceProjection(rows()[:-1], gates(), "READY_FOR_OWNER_MERGE",
                                  "DEMONSTRATED")
        self.assertIs(caught.exception.spec, SCHOOL.BAMF_DELIVERY.INVALID)

    def test_executed_pass_requires_fresh_complete_independent_evidence(self):
        incomplete = evidence(fresh_run_receipt="PENDING")
        with self.assertRaises(BilqisError) as caught:
            admitted_state(ProofState.EXECUTED_PASS, incomplete,
                           current_identity=incomplete.identity())
        self.assertIs(caught.exception.spec, SCHOOL.BAMF_DELIVERY.INVALID)

    def test_failure_gate_precedes_green_evidence(self):
        complete = evidence()
        self.assertIs(admitted_state(
            ProofState.EXECUTED_PASS, complete,
            current_identity=complete.identity(),
            failure_gates=("GRADE_NEUTRAL_INVARIANCE_FAILED",)),
            ProofState.EXECUTED_FAIL)

    def test_identity_drift_requires_requalification_before_pass(self):
        complete = evidence()
        current = (complete.source_digest, "e" * 64, complete.issue_digest)
        self.assertIs(admitted_state(
            ProofState.EXECUTED_PASS, complete, current_identity=current),
            ProofState.REQUALIFICATION_REQUIRED)

    def test_ready_refuses_code_present_rows(self):
        with self.assertRaises(BilqisError) as caught:
            ConformanceProjection(rows(), gates(), "READY_FOR_OWNER_MERGE", "NOT_CLAIMED")
        self.assertIs(caught.exception.spec, SCHOOL.BAMF_DELIVERY.INVALID)

    def test_failed_global_gate_forces_blocked_delivery(self):
        failed_gates = (
            FailureGate("GRADE_NEUTRAL_INVARIANCE", "tests/grade_neutral.py",
                        ProofState.EXECUTED_FAIL, "grade permutation changed selection"),
            gates()[1],
        )
        with self.assertRaises(BilqisError) as caught:
            ConformanceProjection(rows(), failed_gates, "IN_PROGRESS", "NOT_CLAIMED")
        self.assertIs(caught.exception.spec, SCHOOL.BAMF_DELIVERY.INVALID)


if __name__ == "__main__":
    unittest.main()
