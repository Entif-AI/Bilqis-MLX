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
class ConformanceRow:
    claim_id: str
    owner_ref: str
    contract_ref: str
    test_ref: str
    state: ProofState

    def __post_init__(self) -> None:
        require(self.claim_id in required_claim_ids(), "CONFORMANCE_CLAIM_ID")
        require(all(isinstance(value, str) and value.strip()
                    for value in (self.owner_ref, self.contract_ref, self.test_ref)),
                "CONFORMANCE_ROW_BINDING")
        require(type(self.state) is ProofState, "CONFORMANCE_ROW_STATE")


@dataclass(frozen=True)
class ConformanceProjection:
    rows: tuple[ConformanceRow, ...]
    software_delivery_status: str
    student_mastery_status: str
    schema: str = "bilqis.bamf.delivery-conformance/v1"

    def __post_init__(self) -> None:
        ids = tuple(row.claim_id for row in self.rows)
        require(ids == required_claim_ids(), "CONFORMANCE_COMPLETE_ORDER")
        require(len(set(ids)) == len(ids), "CONFORMANCE_DUPLICATE")
        require(self.software_delivery_status in {
            "IN_PROGRESS", "READY_FOR_OWNER_MERGE", "DELIVERED", "BLOCKED",
        }, "CONFORMANCE_SOFTWARE_STATUS")
        require(self.student_mastery_status in {
            "NOT_CLAIMED", "NOT_RUN", "IN_PROGRESS", "DEMONSTRATED",
        }, "CONFORMANCE_MASTERY_STATUS")

    def to_record(self) -> dict:
        return {
            "schema": self.schema,
            "software_delivery_status": self.software_delivery_status,
            "student_mastery_status": self.student_mastery_status,
            "rows": [asdict(row) for row in self.rows],
        }

    def digest(self) -> str:
        return hashlib.sha256(canonical(self.to_record())).hexdigest()
