"""Strict content-addressed contracts for the C15 delivery boundary."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import hashlib
import json
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL

BAMF_DELIVERY_SCHEMA = "bilqis.bamf.delivery-manifest/v1"
_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def invalid(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.BAMF_DELIVERY.INVALID, reason=reason)


def require(condition: bool, reason: str) -> None:
    if not condition:
        invalid(reason)


def _name(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\n" not in value


def _sha(value: object) -> bool:
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _tuple(value: object, item_type: type, key) -> bool:
    return (type(value) is tuple and all(type(item) is item_type for item in value)
            and tuple(sorted(value, key=key)) == value
            and len({key(item) for item in value}) == len(value))


class ReceiptStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    PROVISIONAL = "PROVISIONAL"
    BLOCKED = "BLOCKED"


class ProofState(StrEnum):
    MENTIONED = "MENTIONED"
    SPECIFIED = "SPECIFIED"
    CODE_PRESENT = "CODE_PRESENT"
    EXECUTED_PASS = "EXECUTED_PASS"
    EXECUTED_FAIL = "EXECUTED_FAIL"
    BLOCKED = "BLOCKED"
    REQUALIFICATION_REQUIRED = "REQUALIFICATION_REQUIRED"


class EgmStatus(StrEnum):
    PENDING = "EGM_PENDING"
    PASS = "EGM_PASS"
    FAIL = "EGM_FAIL"


@dataclass(frozen=True)
class ComponentReceipt:
    component_id: str
    owner_issue: int
    head_sha: str
    status: ReceiptStatus
    evidence_ref: str

    def __post_init__(self) -> None:
        require(_name(self.component_id) and type(self.owner_issue) is int
                and self.owner_issue > 0 and _sha(self.head_sha)
                and type(self.status) is ReceiptStatus and _name(self.evidence_ref),
                "COMPONENT_RECEIPT")


@dataclass(frozen=True)
class IssueReceipt:
    issue: int
    issue_key: str
    state: str
    status: ReceiptStatus
    head_sha: str
    evidence_ref: str

    def __post_init__(self) -> None:
        require(type(self.issue) is int and self.issue > 0 and _name(self.issue_key)
                and self.state in {"OPEN", "CLOSED"}
                and type(self.status) is ReceiptStatus and _sha(self.head_sha)
                and _name(self.evidence_ref), "ISSUE_RECEIPT")


@dataclass(frozen=True)
class CommitReceipt:
    sha: str
    owner_issue: int
    role: str

    def __post_init__(self) -> None:
        require(_sha(self.sha) and type(self.owner_issue) is int
                and self.owner_issue > 0 and _name(self.role), "COMMIT_RECEIPT")


@dataclass(frozen=True)
class ProofReceipt:
    proof_id: str
    state: ProofState
    input_schema: str
    output_schema: str
    evidence_ref: str
    observed: str

    def __post_init__(self) -> None:
        require(_name(self.proof_id) and type(self.state) is ProofState
                and all(_name(item) for item in (self.input_schema, self.output_schema,
                                                  self.evidence_ref, self.observed)),
                "PROOF_RECEIPT")


@dataclass(frozen=True)
class EgmReceipt:
    reviewer: str
    status: EgmStatus
    candidate_sha: str
    report_ref: str

    def __post_init__(self) -> None:
        require(_name(self.reviewer) and type(self.status) is EgmStatus
                and _sha(self.candidate_sha) and _name(self.report_ref), "EGM_RECEIPT")


@dataclass(frozen=True)
class OperatorCommandReceipt:
    command_id: str
    argv: tuple[str, ...]
    state: ProofState
    parser_test: str
    evidence_ref: str

    def __post_init__(self) -> None:
        require(_name(self.command_id) and type(self.argv) is tuple and bool(self.argv)
                and all(_name(item) for item in self.argv)
                and type(self.state) is ProofState and _name(self.parser_test)
                and _name(self.evidence_ref), "OPERATOR_COMMAND_RECEIPT")


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


@dataclass(frozen=True)
class BamfDeliveryManifest:
    components: tuple[ComponentReceipt, ...]
    issues: tuple[IssueReceipt, ...]
    commits: tuple[CommitReceipt, ...]
    proofs: tuple[ProofReceipt, ...]
    egm: tuple[EgmReceipt, ...]
    operator_commands: tuple[OperatorCommandReceipt, ...]
    software_delivery_status: str = "IN_PROGRESS"
    student_mastery_status: str = "NOT_CLAIMED"
    schema: str = BAMF_DELIVERY_SCHEMA

    def __post_init__(self) -> None:
        require(self.schema == BAMF_DELIVERY_SCHEMA, "MANIFEST_SCHEMA")
        require(_tuple(self.components, ComponentReceipt, lambda item: item.component_id),
                "MANIFEST_COMPONENTS")
        require(_tuple(self.issues, IssueReceipt, lambda item: item.issue), "MANIFEST_ISSUES")
        require(_tuple(self.commits, CommitReceipt, lambda item: item.sha), "MANIFEST_COMMITS")
        require(_tuple(self.proofs, ProofReceipt, lambda item: item.proof_id), "MANIFEST_PROOFS")
        require(_tuple(self.egm, EgmReceipt, lambda item: item.reviewer), "MANIFEST_EGM")
        require(_tuple(self.operator_commands, OperatorCommandReceipt,
                       lambda item: item.command_id), "MANIFEST_OPERATOR_COMMANDS")
        require(self.software_delivery_status in {
            "IN_PROGRESS", "READY_FOR_OWNER_MERGE", "DELIVERED", "BLOCKED",
        }, "SOFTWARE_DELIVERY_STATUS")
        require(self.student_mastery_status in {
            "NOT_CLAIMED", "NOT_RUN", "IN_PROGRESS", "DEMONSTRATED",
        }, "STUDENT_MASTERY_STATUS")

    def to_record(self) -> dict:
        return {
            "schema": self.schema,
            "components": [asdict(item) for item in self.components],
            "issues": [asdict(item) for item in self.issues],
            "commits": [asdict(item) for item in self.commits],
            "proofs": [asdict(item) for item in self.proofs],
            "egm": [asdict(item) for item in self.egm],
            "operator_commands": [asdict(item) for item in self.operator_commands],
            "software_delivery_status": self.software_delivery_status,
            "student_mastery_status": self.student_mastery_status,
        }

    def digest(self) -> str:
        return hashlib.sha256(canonical(self.to_record())).hexdigest()
