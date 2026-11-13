import copy
import json
from pathlib import Path
import subprocess
import unittest

from bilqis_mlx.errors import BilqisError, SCHOOL
from bilqis_mlx.runtime.delivery import ProofState
from bilqis_mlx.runtime.delivery.conformance import (
    AuthorityIdentity, ConformanceProjection, ConformanceRow, EvidenceBinding,
    ExecutionReceipt, FailureGate, load_conformance_record, required_claim_ids,
)
from bilqis_mlx.runtime.delivery.sources import (
    authority_identity, expected_behavior, item_by_key, literal_test_ref,
    requirement_texts, validate_executed_pass,
)


def inert_evidence():
    return EvidenceBinding(
        "literal acceptance clause", "BAMF-0.2-SPEC-001@v0.2.0", 539,
        "PENDING_DIRECT_OWNER_COMMIT_BINDING",
        "docs/architecture/BAMF_0_2.md#requirements-continuity",
        "BLOCKED_SOURCE_OWNER:test", "independent expected behavior",
        "NOT_EXECUTED", "PENDING_CURRENT_HEAD_RUNNER", None, "PENDING",
        AuthorityIdentity("a" * 64, "b" * 64, "c" * 64))


def rows():
    return tuple(ConformanceRow(
        claim_id, "docs/tasks/bamf-0.2/ISSUE_BOOK.md",
        "docs/architecture/BAMF_0_2.md", f"tests/{claim_id}.py",
        ProofState.SPECIFIED, inert_evidence()) for claim_id in required_claim_ids())


def gates(state=ProofState.CODE_PRESENT):
    return (
        FailureGate("GRADE_NEUTRAL_INVARIANCE", "tests/grade_neutral.py",
                    state, "current-head witness"),
        FailureGate("NO_LEGACY_BAV_RUNTIME_NAMESPACE", "tests/no_bav.py",
                    state, "current-head witness"),
    )


def forged_pass_row():
    candidate = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True).strip()
    fixture = literal_test_ref("A01", "BAMF-REQ-001")
    expected = expected_behavior("A01", "BAMF-REQ-001")
    observed = "fabricated observed pass"
    runner = "fabricated runner"
    receipt = ExecutionReceipt.from_execution(
        receipt_ref="docs/evidence/bamf/delivery/runs/forged.json",
        candidate_sha=candidate, fixture=fixture, expected=expected,
        observed=observed, runner=runner, disposition="PASS")
    evidence = EvidenceBinding(
        requirement_texts()["BAMF-REQ-001"], "BAMF-0.2-SPEC-001@v0.2.0",
        item_by_key("A01")["number"], candidate,
        "docs/architecture/BAMF_0_2.md#requirements-continuity",
        fixture, expected, observed, runner, receipt, "PASS",
        authority_identity("A01"))
    return ConformanceRow(
        "BAMF-REQ-001", "A01/A02/A12",
        "docs/architecture/BAMF_0_2.md#requirements-continuity",
        fixture, ProofState.EXECUTED_PASS, evidence)


class ConformanceProjectionTests(unittest.TestCase):
    def test_projection_requires_all_24_requirements_and_20_failures_in_order(self):
        value = ConformanceProjection(rows(), gates(), "IN_PROGRESS", "NOT_CLAIMED")
        self.assertEqual(len(value.rows), 44)
        self.assertEqual(value.rows[0].claim_id, "BAMF-REQ-001")
        self.assertEqual(value.rows[-1].claim_id, "F20")

    def test_malformed_authority_digest_is_rejected(self):
        with self.assertRaises(BilqisError):
            AuthorityIdentity("not-a-digest", "b" * 64, "c" * 64)

    def test_forged_pass_without_repository_receipt_file_is_rejected(self):
        with self.assertRaises(BilqisError):
            validate_executed_pass(forged_pass_row())

    def test_untracked_local_receipt_cannot_satisfy_commit_bound_pass(self):
        row = forged_pass_row()
        root = Path(__file__).resolve().parents[4]
        path = root / row.evidence.run_receipt.receipt_ref
        path.parent.mkdir(parents=True, exist_ok=True)
        receipt = row.evidence.run_receipt
        path.write_text(json.dumps({
            "schema": receipt.schema,
            "receipt_ref": receipt.receipt_ref,
            "candidate_sha": receipt.candidate_sha,
            "fixture_sha256": receipt.fixture_sha256,
            "expected_sha256": receipt.expected_sha256,
            "observed_sha256": receipt.observed_sha256,
            "runner_sha256": receipt.runner_sha256,
            "disposition": receipt.disposition,
        }))
        try:
            with self.assertRaises(BilqisError):
                validate_executed_pass(row)
        finally:
            path.unlink(missing_ok=True)

    def test_projection_rejects_forged_executed_pass(self):
        forged = forged_pass_row()
        candidate_rows = (forged, *rows()[1:])
        with self.assertRaises(BilqisError) as caught:
            ConformanceProjection(candidate_rows, gates(), "IN_PROGRESS", "NOT_CLAIMED")
        self.assertIs(caught.exception.spec, SCHOOL.BAMF_DELIVERY.INVALID)

    def test_ready_refuses_nonexecuted_rows(self):
        with self.assertRaises(BilqisError) as caught:
            ConformanceProjection(rows(), gates(ProofState.EXECUTED_PASS),
                                  "READY_FOR_OWNER_MERGE", "NOT_CLAIMED")
        self.assertIs(caught.exception.spec, SCHOOL.BAMF_DELIVERY.INVALID)

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
