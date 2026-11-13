"""Exact C15.1b projection over all BAMF requirements and failure families."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import re

from bilqis_mlx.runtime.delivery.contracts import ProofState, canonical, require

CONFORMANCE_SCHEMA = "bilqis.bamf.delivery-conformance/v2"
_SHA40 = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


@dataclass(frozen=True)
class AuthorityIdentity:
    source_digest: str
    contract_digest: str
    issue_digest: str

    def __post_init__(self) -> None:
        require(all(_digest(value) for value in (
            self.source_digest, self.contract_digest, self.issue_digest)),
            "CONFORMANCE_AUTHORITY_DIGEST")

    @classmethod
    def from_authorities(cls, *, source: bytes, contract: bytes,
                         issue: bytes) -> "AuthorityIdentity":
        require(all(type(value) is bytes for value in (source, contract, issue)),
                "CONFORMANCE_AUTHORITY_BYTES")
        return cls(_sha256(source), _sha256(contract), _sha256(issue))


@dataclass(frozen=True)
class ExecutionReceipt:
    schema: str
    candidate_sha: str
    fixture_sha256: str
    expected_sha256: str
    observed_sha256: str
    runner_sha256: str
    disposition: str

    def __post_init__(self) -> None:
        require(self.schema == "bilqis.bamf.execution-receipt/v1",
                "CONFORMANCE_RUN_RECEIPT_SCHEMA")
        require(isinstance(self.candidate_sha, str)
                and _SHA40.fullmatch(self.candidate_sha) is not None,
                "CONFORMANCE_RUN_RECEIPT_CANDIDATE")
        require(all(_digest(value) for value in (
            self.fixture_sha256, self.expected_sha256, self.observed_sha256,
            self.runner_sha256)), "CONFORMANCE_RUN_RECEIPT_DIGEST")
        require(self.disposition in {"PASS", "FAIL"},
                "CONFORMANCE_RUN_RECEIPT_DISPOSITION")

    @classmethod
    def from_execution(cls, *, candidate_sha: str, fixture: str,
                       expected: str, observed: str, runner: str,
                       disposition: str) -> "ExecutionReceipt":
        values = (fixture, expected, observed, runner)
        require(all(isinstance(value, str) and value.strip() for value in values),
                "CONFORMANCE_RUN_RECEIPT_INPUT")
        return cls(
            "bilqis.bamf.execution-receipt/v1", candidate_sha,
            *(_sha256(value.encode()) for value in values), disposition)

    def verifies(self, *, candidate_sha: str, fixture: str, expected: str,
                 observed: str, runner: str) -> bool:
        return (
            self.candidate_sha == candidate_sha
            and self.fixture_sha256 == _sha256(fixture.encode())
            and self.expected_sha256 == _sha256(expected.encode())
            and self.observed_sha256 == _sha256(observed.encode())
            and self.runner_sha256 == _sha256(runner.encode())
        )


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
    run_receipt: ExecutionReceipt | None
    reviewer_decision: str
    authority_identity: AuthorityIdentity

    def __post_init__(self) -> None:
        strings = (
            self.normative_text, self.variant_revision, self.owner_commit,
            self.contract_path, self.input_fixture, self.expected_behavior,
            self.observed_output, self.runner_environment, self.reviewer_decision,
        )
        require(type(self.owner_issue) is int and self.owner_issue > 0,
                "CONFORMANCE_EVIDENCE_OWNER")
        require(all(isinstance(value, str) and value.strip() for value in strings),
                "CONFORMANCE_EVIDENCE_BINDING")
        require(self.run_receipt is None or type(self.run_receipt) is ExecutionReceipt,
                "CONFORMANCE_EVIDENCE_RUN_RECEIPT")
        require(type(self.authority_identity) is AuthorityIdentity,
                "CONFORMANCE_EVIDENCE_AUTHORITY")

    def complete_for_pass(self) -> bool:
        return (
            self.reviewer_decision == "PASS"
            and _SHA40.fullmatch(self.owner_commit) is not None
            and self.run_receipt is not None
            and self.run_receipt.disposition == "PASS"
            and self.run_receipt.verifies(
                candidate_sha=self.owner_commit, fixture=self.input_fixture,
                expected=self.expected_behavior, observed=self.observed_output,
                runner=self.runner_environment)
        )


def admitted_state(requested: ProofState, evidence: EvidenceBinding, *,
                   source: bytes, contract: bytes, issue: bytes,
                   failure_gates: tuple[str, ...] = ()) -> ProofState:
    """Apply failure/drift precedence before admitting an evidence state."""
    require(type(requested) is ProofState, "CONFORMANCE_REQUESTED_STATE")
    current_identity = AuthorityIdentity.from_authorities(
        source=source, contract=contract, issue=issue)
    require(type(failure_gates) is tuple
            and all(isinstance(value, str) and value.strip() for value in failure_gates),
            "CONFORMANCE_FAILURE_GATES")
    if failure_gates:
        return ProofState.EXECUTED_FAIL
    if evidence.authority_identity != current_identity:
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
    schema: str = CONFORMANCE_SCHEMA

    def __post_init__(self) -> None:
        require(self.schema == CONFORMANCE_SCHEMA, "CONFORMANCE_SCHEMA")
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


_CONFORMANCE_KEYS = frozenset((
    "schema", "software_delivery_status", "student_mastery_status", "rows",
    "failure_gates", "conformance_sha256",
))


def load_conformance_record(record: object) -> ConformanceProjection:
    """Strictly decode v2; legacy/v1 shapes are refused rather than guessed."""
    require(type(record) is dict and set(record) == _CONFORMANCE_KEYS,
            "CONFORMANCE_RECORD_KEYS")
    require(record.get("schema") == CONFORMANCE_SCHEMA, "CONFORMANCE_RECORD_SCHEMA")
    try:
        rows = []
        for item in record["rows"]:
            require(type(item) is dict, "CONFORMANCE_ROW_RECORD")
            evidence = item["evidence"]
            require(type(evidence) is dict, "CONFORMANCE_EVIDENCE_RECORD")
            identity = AuthorityIdentity(**evidence["authority_identity"])
            receipt_raw = evidence["run_receipt"]
            receipt = None if receipt_raw is None else ExecutionReceipt(**receipt_raw)
            binding = EvidenceBinding(
                evidence["normative_text"], evidence["variant_revision"],
                evidence["owner_issue"], evidence["owner_commit"],
                evidence["contract_path"], evidence["input_fixture"],
                evidence["expected_behavior"], evidence["observed_output"],
                evidence["runner_environment"], receipt,
                evidence["reviewer_decision"], identity)
            rows.append(ConformanceRow(
                item["claim_id"], item["owner_ref"], item["contract_ref"],
                item["test_ref"], ProofState(item["state"]), binding))
        gates = tuple(FailureGate(
            item["gate_id"], item["test_ref"], ProofState(item["state"]),
            item["observed"]) for item in record["failure_gates"])
        value = ConformanceProjection(
            tuple(rows), gates, record["software_delivery_status"],
            record["student_mastery_status"], schema=record["schema"])
    except (KeyError, TypeError, ValueError):
        require(False, "CONFORMANCE_RECORD_VALUE")
        raise AssertionError("unreachable")
    require(record["conformance_sha256"] == value.digest(), "CONFORMANCE_RECORD_DIGEST")
    return value
