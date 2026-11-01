"""A09.4 immutable progress/status contracts and verified staging bridge."""
from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum
import hashlib

from .atlas_frontier_contracts import CurriculumSnapshot, _bytes, _fail
from .atlas_frontier_selection import FrontierDeltaSelection
from .executable_release import ExecutableFactoryRelease


class FrontierStatus(str, Enum):
    PROPOSAL = "PROPOSAL"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"
    FIXED_POINT = "FIXED_POINT"
    WAITING_FOR_EVIDENCE = "WAITING_FOR_EVIDENCE"
    SOURCE_HELD = "SOURCE_HELD"
    IMPLEMENTATION_UNCOVERED = "IMPLEMENTATION_UNCOVERED"
    LEASE_REQUIRED = "LEASE_REQUIRED"
    COMPLETE_ATLAS_COVERAGE = "COMPLETE_ATLAS_COVERAGE"


@dataclass(frozen=True, order=True)
class FrontierRemediation:
    semantic_id: str
    family_id: str
    status: FrontierStatus
    code: str
    owner: str
    dependency_id: str = ""


@dataclass(frozen=True)
class StagedSelectionReceipt:
    """Proof that one exact A09.3 selection became one verified staged successor."""

    selection: FrontierDeltaSelection
    predecessor_release: ExecutableFactoryRelease
    staged_successor: ExecutableFactoryRelease
    receipt_sha256: str
    schema: str = "bilqis.factory-staged-selection-receipt/v1"

    @property
    def staged_successor_sha256(self) -> str:
        return self.staged_successor.release_sha256

    @property
    def selected_semantic_id(self) -> str:
        return self.selection.selected_semantic_id

    def expected_digest(self) -> str:
        return hashlib.sha256(_bytes({
            field.name: getattr(self, field.name)
            for field in fields(self) if field.name != "receipt_sha256"
        })).hexdigest()

    def verify(self) -> None:
        self.selection.verify()
        self.predecessor_release.verify()
        self.staged_successor.verify_successor_of(self.predecessor_release)
        transition = self.staged_successor.transition
        previous = self.predecessor_release.semantic_catalog
        current = self.staged_successor.semantic_catalog
        if (self.schema != "bilqis.factory-staged-selection-receipt/v1"
                or self.selection.admitted_release_sha256
                != self.predecessor_release.release_sha256
                or transition is None
                or transition.added_capabilities
                   != self.selection.introduced_capability_ids
                or transition.removed_capabilities
                or transition.changed_capabilities
                or current[:len(previous)] != previous
                or tuple(current[len(previous):])
                   != self.selection.introduced_semantic_ids
                or self.receipt_sha256 != self.expected_digest()):
            _fail("BAMF_PLANNER_STAGED_SELECTION_INVALID")


@dataclass(frozen=True)
class FrontierProgress:
    input_snapshot_sha256: str
    planning_snapshot: CurriculumSnapshot
    status: FrontierStatus
    proposal_selection_sha256: str | None
    staged_receipts: tuple[StagedSelectionReceipt, ...]
    pending_staged_receipt_sha256: str | None
    source_held_count: int
    implementation_uncovered_count: int
    waiting_for_evidence_count: int
    ready_count: int
    remediation: tuple[FrontierRemediation, ...]
    progress_sha256: str
    schema: str = "bilqis.factory-atlas-frontier-progress/v1"

    @property
    def snapshot_sha256(self) -> str:
        return self.planning_snapshot.snapshot_sha256

    @property
    def coverage_epoch_sha256(self) -> str:
        return self.planning_snapshot.snapshot_sha256

    @property
    def cursor(self) -> int:
        return self.planning_snapshot.cursor

    @property
    def requested_semantic_ids(self) -> tuple[str, ...]:
        return tuple(sorted(set(
            receipt.selected_semantic_id for receipt in self.staged_receipts)))

    @property
    def pending_receipt(self) -> StagedSelectionReceipt | None:
        return next((receipt for receipt in self.staged_receipts
                     if receipt.receipt_sha256
                     == self.pending_staged_receipt_sha256), None)

    @property
    def pending_staged_successor_sha256(self) -> str | None:
        receipt = self.pending_receipt
        return None if receipt is None else receipt.staged_successor_sha256

    @property
    def pending_semantic_id(self) -> str | None:
        receipt = self.pending_receipt
        return None if receipt is None else receipt.selected_semantic_id

    def expected_digest(self) -> str:
        return hashlib.sha256(_bytes({
            field.name: getattr(self, field.name)
            for field in fields(self) if field.name != "progress_sha256"
        })).hexdigest()

    def verify(self) -> None:
        self.planning_snapshot.verify()
        if (self.schema != "bilqis.factory-atlas-frontier-progress/v1"
                or not self.input_snapshot_sha256
                or (self.planning_snapshot.snapshot_sha256
                    != self.input_snapshot_sha256
                    and self.planning_snapshot.predecessor_sha256
                    != self.input_snapshot_sha256)
                or self.staged_receipts != tuple(sorted(
                    self.staged_receipts, key=lambda item: item.receipt_sha256))
                or len({item.receipt_sha256 for item in self.staged_receipts})
                   != len(self.staged_receipts)
                or len({item.staged_successor_sha256 for item in self.staged_receipts})
                   != len(self.staged_receipts)
                or min(self.source_held_count, self.implementation_uncovered_count,
                       self.waiting_for_evidence_count, self.ready_count) < 0):
            _fail("BAMF_PLANNER_PROGRESS_INVALID")
        for receipt in self.staged_receipts:
            receipt.verify()
        if (self.pending_staged_receipt_sha256 is not None
                and self.pending_receipt is None):
            _fail("BAMF_PLANNER_PROGRESS_PENDING_RECEIPT_INVALID")
        if self.pending_receipt is not None:
            if (self.status is not FrontierStatus.LEASE_REQUIRED
                    or self.pending_receipt.staged_successor_sha256
                       not in self.planning_snapshot.staged_factory_release_sha256s
                    or self.pending_receipt.staged_successor_sha256
                       == self.planning_snapshot.admitted_factory_release_sha256):
                _fail("BAMF_PLANNER_PROGRESS_PENDING_RECEIPT_INVALID")
        elif self.status is FrontierStatus.LEASE_REQUIRED:
            _fail("BAMF_PLANNER_PROGRESS_PENDING_RECEIPT_REQUIRED")
        if self.progress_sha256 != self.expected_digest():
            _fail("BAMF_PLANNER_PROGRESS_DIGEST_MISMATCH")
