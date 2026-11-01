"""A09.4 validation of direct and resumed frontier progress credit."""
from __future__ import annotations

from dataclasses import replace
import hashlib

from .atlas_frontier_closure import ClosureStatus, FrontierClosure
from .atlas_frontier_contracts import CurriculumSnapshot, _bytes, _fail
from .atlas_frontier_progress_contracts import FrontierProgress, StagedSelectionReceipt
from .atlas_frontier_selection import (
    DeferredClosure,
    FrontierDeltaSelection,
    _candidate_signature,
    _ranked_ready_targets,
    validate_frontier_selection,
)
from .atlas_frontier_selection_validation import TargetDeltaProjection
from .executable_release import ExecutableFactoryRelease


def obligation_digest(rows) -> str:
    return hashlib.sha256(_bytes(tuple(
        (row.family_id, row.source_evidence_sha256, row.prerequisites)
        for row in sorted(rows)))).hexdigest()


def current_obligations(closure: FrontierClosure) -> dict[str, str]:
    return {
        identity: obligation_digest(tuple(
            row for row in closure.candidates if row.semantic_id == identity))
        for identity in closure.constituent_order
    }


def validate_prior(snapshot: CurriculumSnapshot, prior: FrontierProgress | None) -> None:
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


def validate_direct_selection(
    snapshot: CurriculumSnapshot,
    closure: FrontierClosure,
    selection: FrontierDeltaSelection | None,
    current_release: ExecutableFactoryRelease | None,
    selected_projection: TargetDeltaProjection | None,
    staged_receipt: StagedSelectionReceipt | None,
) -> tuple[ExecutableFactoryRelease | None, TargetDeltaProjection | None]:
    if selection is None:
        if current_release is not None or selected_projection is not None:
            _fail("BAMF_PLANNER_SELECTION_INPUT_INVALID")
        return None, None
    if (current_release is None and selected_projection is None
            and staged_receipt is not None):
        current_release = staged_receipt.predecessor_release
        selected_projection = staged_receipt.projection
    if current_release is None or selected_projection is None:
        _fail("BAMF_PLANNER_SELECTION_INPUT_INVALID")
    validate_frontier_selection(
        snapshot, closure, selection, current_release, selected_projection)
    return current_release, selected_projection


def validate_staged_receipt(
    snapshot: CurriculumSnapshot,
    selection: FrontierDeltaSelection | None,
    receipt: StagedSelectionReceipt | None,
    current_release: ExecutableFactoryRelease | None,
    selected_projection: TargetDeltaProjection | None,
) -> None:
    if receipt is None:
        return
    receipt.verify()
    if (selection is None
            or receipt.selection != selection
            or receipt.predecessor_release != current_release
            or receipt.projection != selected_projection
            or receipt.staged_successor_sha256
               not in snapshot.staged_factory_release_sha256s):
        _fail("BAMF_PLANNER_STAGED_SELECTION_MISMATCH")


def requested_keys(
    receipts: tuple[StagedSelectionReceipt, ...] | list[StagedSelectionReceipt],
) -> set[tuple[str, str]]:
    return {(receipt.selected_semantic_id,
             obligation_digest(receipt.selection.selected_obligations))
            for receipt in receipts}


def has_unrequested_ready(
    closure: FrontierClosure,
    receipts: tuple[StagedSelectionReceipt, ...] | list[StagedSelectionReceipt],
    current: dict[str, str],
) -> bool:
    requested = requested_keys(receipts)
    for semantic_id in closure.constituent_order:
        rows = tuple(
            row for row in closure.candidates if row.semantic_id == semantic_id)
        if (rows and all(row.status is ClosureStatus.READY for row in rows)
                and (semantic_id, current[semantic_id]) not in requested):
            return True
    return False


def _receipt_obligation_current(
    receipt: StagedSelectionReceipt,
    current: dict[str, str],
) -> bool:
    return current.get(receipt.selected_semantic_id) == obligation_digest(
        receipt.selection.selected_obligations)


def _validation_context(
    snapshot: CurriculumSnapshot,
    closure: FrontierClosure,
    receipt: StagedSelectionReceipt,
    planner_predecessor: CurriculumSnapshot | None = None,
) -> tuple[CurriculumSnapshot, FrontierClosure]:
    comparator = planner_predecessor or receipt.selection
    if planner_predecessor is not None:
        if (receipt.selection.snapshot_sha256
                != planner_predecessor.snapshot_sha256
                or receipt.predecessor_release.release_sha256
                != planner_predecessor.admitted_factory_release_sha256):
            _fail("BAMF_PLANNER_SELECTION_INVALID")
    bound_snapshot = replace(
        snapshot,
        admitted_factory_release_sha256=receipt.predecessor_release.release_sha256,
        policy_epoch=comparator.policy_epoch,
        cursor=comparator.cursor,
        snapshot_sha256="0" * 64,
    )
    bound_snapshot = replace(
        bound_snapshot, snapshot_sha256=bound_snapshot.expected_digest())
    bound_closure = replace(
        closure,
        snapshot_sha256=bound_snapshot.snapshot_sha256,
        closure_sha256="0" * 64,
    )
    return bound_snapshot, replace(
        bound_closure, closure_sha256=bound_closure.expected_digest())


def _revalidate_receipt_selection(
    snapshot: CurriculumSnapshot,
    closure: FrontierClosure,
    receipt: StagedSelectionReceipt,
    planner_predecessor: CurriculumSnapshot | None = None,
) -> bool:
    bound_snapshot, bound_closure = _validation_context(
        snapshot, closure, receipt, planner_predecessor)
    _, ranked = _ranked_ready_targets(bound_snapshot, bound_closure)
    target = next(
        (item for item in ranked if item[3] == receipt.selected_semantic_id),
        None,
    )
    if target is None:
        return False
    slope, neg_unlocks, _, identity, rows = target
    selected_keys = {(item.semantic_id, item.family_id) for item in rows}
    deferred = tuple(sorted(DeferredClosure(
        item.semantic_id,
        item.family_id,
        item.status,
        item.reasons,
    ) for item in bound_closure.candidates
        if (item.semantic_id, item.family_id) not in selected_keys))
    rebound = replace(
        receipt.selection,
        snapshot_sha256=bound_snapshot.snapshot_sha256,
        closure_sha256=bound_closure.closure_sha256,
        admitted_release_sha256=receipt.predecessor_release.release_sha256,
        selected_obligations=rows,
        prerequisite_slope=slope,
        downstream_unlocks=-neg_unlocks,
        deferred=deferred,
        candidate_signature=_candidate_signature(
            identity,
            rows,
            receipt.selection.introduced_capability_ids,
            receipt.selection.introduced_semantic_ids,
        ),
        selection_sha256="0" * 64,
    )
    rebound = replace(rebound, selection_sha256=rebound.expected_digest())
    validate_frontier_selection(
        bound_snapshot,
        bound_closure,
        rebound,
        receipt.predecessor_release,
        receipt.projection,
    )
    return True


def credited_receipts(
    snapshot: CurriculumSnapshot,
    closure: FrontierClosure,
    receipts: tuple[StagedSelectionReceipt, ...] | list[StagedSelectionReceipt],
    current: dict[str, str],
    *,
    planner_predecessor: CurriculumSnapshot | None = None,
    pending_receipt_sha256: str | None = None,
) -> list[StagedSelectionReceipt]:
    credited = []
    for receipt in receipts:
        if not _receipt_obligation_current(receipt, current):
            continue
        comparator = (
            planner_predecessor
            if receipt.receipt_sha256 == pending_receipt_sha256 else None
        )
        if _revalidate_receipt_selection(
                snapshot, closure, receipt, comparator):
            credited.append(receipt)
    return credited
