"""Exact C15.1b projection over all BAMF requirements and failure families."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib

from bilqis_mlx.runtime.delivery.contracts import ProofState, canonical, require


def required_claim_ids() -> tuple[str, ...]:
    requirements = tuple(f"BAMF-REQ-{number:03d}" for number in range(1, 25))
    failures = tuple(f"F{number:02d}" for number in range(1, 21))
    return requirements + failures


@dataclass(frozen=True)
class EvidenceBinding:
    normative_text: str
    variant_revision: str
    owner_issue: int
    owner_commit: str
    contract_path: str
    input_fixture: str
    expected_behavior: str
    observed_output: str
    runner_environment: str
    fresh_run_receipt: str
    reviewer_decision: str
    source_digest: str
    contract_digest: str
    issue_digest: str

    def __post_init__(self) -> None:
        strings = (
            self.normative_text, self.variant_revision, self.owner_commit,
            self.contract_path, self.input_fixture, self.expected_behavior,
            self.observed_output, self.runner_environment, self.fresh_run_receipt,
            self.reviewer_decision, self.source_digest, self.contract_digest,
            self.issue_digest,
        )
        require(type(self.owner_issue) is int and self.owner_issue > 0,
                "CONFORMANCE_EVIDENCE_OWNER")
        require(all(isinstance(value, str) and value.strip() for value in strings),
                "CONFORMANCE_EVIDENCE_BINDING")

    def complete_for_pass(self) -> bool:
        return (
            self.reviewer_decision == "PASS"
            and len(self.owner_commit) in {40, 64}
            and all(character in "0123456789abcdef" for character in self.owner_commit)
            and self.fresh_run_receipt not in {"NOT_EXECUTED", "BLOCKED", "PENDING"}
            and self.observed_output not in {"NOT_EXECUTED", "BLOCKED", "PENDING"}
        )

    def identity(self) -> tuple[str, str, str]:
        return self.source_digest, self.contract_digest, self.issue_digest


def admitted_state(requested: ProofState, evidence: EvidenceBinding, *,
                   current_identity: tuple[str, str, str],
                   failure_gates: tuple[str, ...] = ()) -> ProofState:
    """Apply failure/drift precedence before admitting an evidence state."""
    require(type(requested) is ProofState, "CONFORMANCE_REQUESTED_STATE")
    require(type(current_identity) is tuple and len(current_identity) == 3
            and all(isinstance(value, str) and value.strip()
                    for value in current_identity), "CONFORMANCE_CURRENT_IDENTITY")
    require(type(failure_gates) is tuple
            and all(isinstance(value, str) and value.strip() for value in failure_gates),
            "CONFORMANCE_FAILURE_GATES")
    if failure_gates:
        return ProofState.EXECUTED_FAIL
    if evidence.identity() != current_identity:
        return ProofState.REQUALIFICATION_REQUIRED
    if requested is ProofState.EXECUTED_PASS:
        require(evidence.complete_for_pass(), "CONFORMANCE_EXECUTED_PASS_EVIDENCE")
    return requested


@dataclass(frozen=True)
class FailureGate:
    gate_id: str
    test_ref: str
    state: ProofState
    observed: str

    def __post_init__(self) -> None:
        require(all(isinstance(value, str) and value.strip()
                    for value in (self.gate_id, self.test_ref, self.observed)),
                "CONFORMANCE_FAILURE_GATE_BINDING")
        require(self.state in {ProofState.CODE_PRESENT, ProofState.EXECUTED_PASS,
                               ProofState.EXECUTED_FAIL, ProofState.BLOCKED,
                               ProofState.REQUALIFICATION_REQUIRED},
                "CONFORMANCE_FAILURE_GATE_STATE")


@dataclass(frozen=True)
class ConformanceRow:
    claim_id: str
    owner_ref: str
    contract_ref: str
    test_ref: str
    state: ProofState
    evidence: EvidenceBinding

    def __post_init__(self) -> None:
        require(self.claim_id in required_claim_ids(), "CONFORMANCE_CLAIM_ID")
        require(all(isinstance(value, str) and value.strip()
                    for value in (self.owner_ref, self.contract_ref, self.test_ref)),
                "CONFORMANCE_ROW_BINDING")
        require(type(self.state) is ProofState, "CONFORMANCE_ROW_STATE")
        require(type(self.evidence) is EvidenceBinding, "CONFORMANCE_ROW_EVIDENCE")


@dataclass(frozen=True)
class ConformanceProjection:
    rows: tuple[ConformanceRow, ...]
    failure_gates: tuple[FailureGate, ...]
    software_delivery_status: str
    student_mastery_status: str
    schema: str = "bilqis.bamf.delivery-conformance/v2"

    def __post_init__(self) -> None:
        ids = tuple(row.claim_id for row in self.rows)
        require(ids == required_claim_ids(), "CONFORMANCE_COMPLETE_ORDER")
        require(len(set(ids)) == len(ids), "CONFORMANCE_DUPLICATE")
        gate_ids = tuple(gate.gate_id for gate in self.failure_gates)
        require(gate_ids == ("GRADE_NEUTRAL_INVARIANCE", "NO_LEGACY_BAV_RUNTIME_NAMESPACE"),
                "CONFORMANCE_FAILURE_GATE_SET")
        require(all(type(gate) is FailureGate for gate in self.failure_gates),
                "CONFORMANCE_FAILURE_GATE_TYPE")
        require(self.software_delivery_status in {
            "IN_PROGRESS", "READY_FOR_OWNER_MERGE", "DELIVERED", "BLOCKED",
        }, "CONFORMANCE_SOFTWARE_STATUS")
        require(self.student_mastery_status in {
            "NOT_CLAIMED", "NOT_RUN", "IN_PROGRESS", "DEMONSTRATED",
        }, "CONFORMANCE_MASTERY_STATUS")
        failed = any(row.state is ProofState.EXECUTED_FAIL for row in self.rows)
        failed = failed or any(
            gate.state is ProofState.EXECUTED_FAIL for gate in self.failure_gates)
        if failed:
            require(self.software_delivery_status == "BLOCKED",
                    "CONFORMANCE_FAILURE_PRECEDENCE")
        if self.software_delivery_status in {"READY_FOR_OWNER_MERGE", "DELIVERED"}:
            require(all(row.state is ProofState.EXECUTED_PASS for row in self.rows)
                    and all(gate.state is ProofState.EXECUTED_PASS
                            for gate in self.failure_gates),
                    "CONFORMANCE_READY_REQUIRES_EXECUTED_PASS")

    def to_record(self) -> dict:
        return {
            "schema": self.schema,
            "software_delivery_status": self.software_delivery_status,
            "student_mastery_status": self.student_mastery_status,
            "rows": [asdict(row) for row in self.rows],
            "failure_gates": [asdict(gate) for gate in self.failure_gates],
        }

    def digest(self) -> str:
        return hashlib.sha256(canonical(self.to_record())).hexdigest()
