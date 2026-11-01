"""A09.4 pure resumable progress receipt over closure and bounded selection."""
from __future__ import annotations

from dataclasses import replace
import hashlib

from .atlas_frontier_closure import ClosureStatus, FrontierClosure
from .atlas_frontier_contracts import CurriculumSnapshot, _bytes, _fail
from .atlas_frontier_selection import FrontierDeltaSelection
from .atlas_frontier_selection_validation import validate_closure_structure
from .skos_curriculum import IMPLEMENTATION_UNCOVERED
from .atlas_frontier_progress_contracts import (
    FrontierProgress, FrontierRemediation, FrontierStatus, StagedSelectionReceipt,
)


def _obligation_digest(rows) -> str:
    return hashlib.sha256(_bytes(tuple(
        (row.family_id, row.source_evidence_sha256, row.prerequisites)
        for row in sorted(rows)))).hexdigest()


def _current_obligations(closure: FrontierClosure) -> dict[str, str]:
    return {
        identity: _obligation_digest(tuple(
            row for row in closure.candidates if row.semantic_id == identity))
        for identity in closure.constituent_order
    }


def _counts(closure: FrontierClosure) -> dict[ClosureStatus, int]:
    return {
        status: sum(item.status is status for item in closure.candidates)
        for status in ClosureStatus
    }


def _remediation(closure: FrontierClosure) -> tuple[FrontierRemediation, ...]:
    rows = [FrontierRemediation(
        item.semantic_id, item.family_id, FrontierStatus(item.status.value),
        reason.code, reason.owner, reason.dependency_id,
    ) for item in closure.candidates for reason in item.reasons]
    rows.extend(FrontierRemediation(
        "", "", FrontierStatus.SOURCE_HELD,
        hold.reason_code, hold.owner, hold.source_id,
    ) for hold in closure.source_holds)
    return tuple(sorted(rows))


def _validate_prior(snapshot: CurriculumSnapshot, prior: FrontierProgress | None) -> None:
    if prior is None:
        return
    if type(prior) is not FrontierProgress:
        _fail("BAMF_PLANNER_PROGRESS_PREDECESSOR_INVALID")
    prior.verify()
    if (snapshot.snapshot_sha256 != prior.planning_snapshot.snapshot_sha256
            and snapshot.predecessor_sha256
            != prior.planning_snapshot.snapshot_sha256):
        _fail("BAMF_PLANNER_PROGRESS_PREDECESSOR_MISMATCH")
    eligible = set(snapshot.source_eligible_concept_ids)
    if not set(prior.requested_semantic_ids) <= eligible:
        _fail("BAMF_PLANNER_PROGRESS_PREDECESSOR_SCOPE_DRIFT")


def _advance_cursor_once(
    snapshot: CurriculumSnapshot,
    prior: FrontierProgress,
    constituent_order: tuple[str, ...],
) -> CurriculumSnapshot:
    semantic_id = prior.pending_semantic_id
    if semantic_id not in constituent_order:
        _fail("BAMF_PLANNER_PROGRESS_PENDING_TARGET_MISSING")
    width = len(constituent_order)
    if width == 0:
        _fail("BAMF_PLANNER_PROGRESS_EMPTY_FRONTIER")
    next_cursor = (constituent_order.index(semantic_id) + 1) % width
    if next_cursor == prior.cursor or snapshot.cursor == next_cursor:
        return snapshot
    if snapshot.cursor != prior.cursor:
        _fail("BAMF_PLANNER_PROGRESS_CURSOR_STALE")
    draft = replace(
        snapshot, cursor=next_cursor,
        predecessor_sha256=snapshot.snapshot_sha256,
        snapshot_sha256="0" * 64,
    )
    result = replace(draft, snapshot_sha256=draft.expected_digest())
    result.verify()
    return result


def _selection_current(
    snapshot: CurriculumSnapshot, closure: FrontierClosure,
    selection: FrontierDeltaSelection | None,
) -> None:
    if selection is None:
        return
    selection.verify()
    if (selection.snapshot_sha256 != snapshot.snapshot_sha256
            or selection.closure_sha256 != closure.closure_sha256):
        _fail("BAMF_PLANNER_PROGRESS_SELECTION_MISMATCH")


def _staged_current(
    snapshot: CurriculumSnapshot, selection: FrontierDeltaSelection | None,
    receipt: StagedSelectionReceipt | None,
) -> None:
    if receipt is None:
        return
    receipt.verify()
    if (selection is None
            or receipt.selection != selection
            or receipt.staged_successor_sha256
               not in snapshot.staged_factory_release_sha256s):
        _fail("BAMF_PLANNER_STAGED_SELECTION_MISMATCH")


def _status_without_new_proposal(
    snapshot: CurriculumSnapshot, counts: dict[ClosureStatus, int],
    receipts: tuple[StagedSelectionReceipt, ...], current: dict[str, str],
    source_held_count: int,
    direct_uncovered: int,
) -> FrontierStatus:
    requested = {(receipt.selected_semantic_id,
                  _obligation_digest(receipt.selection.selected_obligations))
                 for receipt in receipts}
    if direct_uncovered:
        return FrontierStatus.IMPLEMENTATION_UNCOVERED
    if counts[ClosureStatus.WAITING_FOR_EVIDENCE]:
        return FrontierStatus.WAITING_FOR_EVIDENCE
    if source_held_count:
        return FrontierStatus.SOURCE_HELD
    complete = (all((key, value) in requested for key, value in current.items())
                and set(current) == set(snapshot.source_eligible_concept_ids))
    if complete:
        return FrontierStatus.COMPLETE_ATLAS_COVERAGE
    return FrontierStatus.FIXED_POINT


def plan_frontier_progress(
    snapshot: CurriculumSnapshot,
    closure: FrontierClosure,
    selection: FrontierDeltaSelection | None = None,
    *,
    prior: FrontierProgress | None = None,
    staged_receipt: StagedSelectionReceipt | None = None,
) -> FrontierProgress:
    """Return one deterministic progress receipt; never stage, lease, or admit."""
    snapshot.verify()
    closure.verify()
    if closure.snapshot_sha256 != snapshot.snapshot_sha256:
        _fail("BAMF_PLANNER_PROGRESS_CLOSURE_MISMATCH")
    validate_closure_structure(snapshot, closure)
    _validate_prior(snapshot, prior)
    _selection_current(snapshot, closure, selection)
    _staged_current(snapshot, selection, staged_receipt)

    current = _current_obligations(closure)
    receipts = list(prior.staged_receipts if prior else ())
    pending_receipt_sha = prior.pending_staged_receipt_sha256 if prior else None
    pending = prior.pending_staged_successor_sha256 if prior else None
    if pending == snapshot.admitted_factory_release_sha256:
        planning_snapshot = _advance_cursor_once(snapshot, prior, closure.constituent_order)
        counts = _counts(closure)
        provisional = FrontierProgress(
            snapshot.snapshot_sha256, planning_snapshot,
            FrontierStatus.FIXED_POINT, None, tuple(sorted(
                receipts, key=lambda item: item.receipt_sha256)),
            None, len(closure.source_holds),
            counts[ClosureStatus.IMPLEMENTATION_UNCOVERED],
            counts[ClosureStatus.WAITING_FOR_EVIDENCE], counts[ClosureStatus.READY],
            _remediation(closure), "0" * 64,
        )
        result = replace(provisional, progress_sha256=provisional.expected_digest())
        result.verify()
        return result
    planning_snapshot = snapshot
    if staged_receipt is not None:
        if (pending_receipt_sha is not None
                and pending_receipt_sha != staged_receipt.receipt_sha256):
            _fail("BAMF_PLANNER_PROGRESS_LEASE_PENDING")
        if staged_receipt.receipt_sha256 not in {
                item.receipt_sha256 for item in receipts}:
            receipts.append(staged_receipt)
        pending_receipt_sha = staged_receipt.receipt_sha256
        pending = staged_receipt.staged_successor_sha256

    counts = _counts(closure)
    direct_uncovered = sum(
        row.implementation_status == IMPLEMENTATION_UNCOVERED
        for row in snapshot.coverage_rows)
    held = len(closure.source_holds)
    proposal = selection.selection_sha256 if selection is not None else None
    if pending is not None and pending != snapshot.admitted_factory_release_sha256:
        status = FrontierStatus.LEASE_REQUIRED
        proposal = None
    elif selection is not None:
        selected_key = (
            selection.selected_semantic_id,
            _obligation_digest(selection.selected_obligations),
        )
        requested = {(receipt.selected_semantic_id,
                      _obligation_digest(receipt.selection.selected_obligations))
                     for receipt in receipts}
        status = (FrontierStatus.FIXED_POINT
                  if selected_key in requested
                  else FrontierStatus.PROPOSAL)
    else:
        requested = {(receipt.selected_semantic_id,
                      _obligation_digest(receipt.selection.selected_obligations))
                     for receipt in receipts}
        unrequested_ready = {
            row.semantic_id for row in closure.candidates
            if row.status is ClosureStatus.READY
            and (row.semantic_id, current[row.semantic_id]) not in requested
        }
        if unrequested_ready:
            _fail("BAMF_PLANNER_PROGRESS_SELECTION_REQUIRED")
        status = _status_without_new_proposal(
            snapshot, counts, tuple(receipts), current, held, direct_uncovered)

    provisional = FrontierProgress(
        snapshot.snapshot_sha256, planning_snapshot, status, proposal,
        tuple(sorted(receipts, key=lambda item: item.receipt_sha256)),
        pending_receipt_sha, held,
        direct_uncovered,
        counts[ClosureStatus.WAITING_FOR_EVIDENCE], counts[ClosureStatus.READY],
        _remediation(closure), "0" * 64,
    )
    result = replace(
        provisional, progress_sha256=provisional.expected_digest())
    result.verify()
    return result
