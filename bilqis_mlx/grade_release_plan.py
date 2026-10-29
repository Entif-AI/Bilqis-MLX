"""Draft disposable-model cutover protocol; no storage, MLX or trainer calls.

This planner consumes observations, not verified admission authority. A future
executor must compose existing grade_transition, vocabulary_growth,
mlx_checkpoint and generation-bound school outboxes. No second journal or
checkpoint format is introduced here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .semantics.foundation.domains import contract_digest, require_sha256


@dataclass(frozen=True)
class CompleteBundleRef:
    model_and_own_adamw_sha256: str
    manifest_sha256: str
    catalog_sha256: str
    optimizer_step: int
    vocabulary_size: int

    def __post_init__(self) -> None:
        for value in (self.model_and_own_adamw_sha256, self.manifest_sha256,
                      self.catalog_sha256):
            require_sha256(value)
        if (type(self.optimizer_step) is not int or self.optimizer_step < 0
                or type(self.vocabulary_size) is not int or self.vocabulary_size < 1):
            raise ValueError("CUTOVER_INVALID_COMPLETE_BUNDLE_REFERENCE")


@dataclass(frozen=True)
class CutoverIntent:
    parent_generation: int
    parent_release: str
    successor_release: str
    parent: CompleteBundleRef
    candidate_package_sha256: str
    independently_pinned_review_sha256: str
    source_release_receipt_sha256: str
    successor_course_sha256: str
    successor_catalog_sha256: str
    successor_vocabulary_size: int

    def __post_init__(self) -> None:
        if (type(self.parent_generation) is not int or self.parent_generation < 0
                or not isinstance(self.parent_release, str) or not self.parent_release.strip()
                or not isinstance(self.successor_release, str) or not self.successor_release.strip()
                or self.parent_release == self.successor_release
                or not isinstance(self.parent, CompleteBundleRef)
                or type(self.successor_vocabulary_size) is not int
                or self.successor_vocabulary_size < self.parent.vocabulary_size):
            raise ValueError("CUTOVER_INVALID_INTENT")
        for value in (self.candidate_package_sha256, self.independently_pinned_review_sha256,
                      self.source_release_receipt_sha256, self.successor_course_sha256,
                      self.successor_catalog_sha256):
            require_sha256(value)

    @property
    def identity(self) -> str:
        return contract_digest(self)


class CutoverAction(str, Enum):
    VERIFY_INDEPENDENT_ADMISSION = "VERIFY_INDEPENDENT_ADMISSION"
    VERIFY_APPEND_ONLY_CATALOG = "VERIFY_APPEND_ONLY_CATALOG"
    VERIFY_DISK_RESERVE = "VERIFY_DISK_RESERVE"
    ALLOCATE_DISPOSABLE_MODEL_AND_OWN_ADAMW = "ALLOCATE_DISPOSABLE_MODEL_AND_OWN_ADAMW"
    STAGE_NEW_COMPLETE_BUNDLE = "STAGE_NEW_COMPLETE_BUNDLE"
    READ_BACK_COMPLETE_BUNDLE = "READ_BACK_COMPLETE_BUNDLE"
    COMMIT_GENERATION_WITH_EXISTING_OUTBOX = "COMMIT_GENERATION_WITH_EXISTING_OUTBOX"
    REPLAY_COMMITTED_EVENTS = "REPLAY_COMMITTED_EVENTS"


class CutoverPlanStatus(str, Enum):
    DRAFT_EXECUTOR_REQUIRED = "DRAFT_DISPOSABLE_EXECUTOR_REQUIRED"
    BLOCKED = "BLOCKED"
    OBSERVED_COMMIT_REQUIRES_EVENT_READBACK = "OBSERVED_COMMIT_REQUIRES_EVENT_READBACK"


@dataclass(frozen=True)
class CutoverObservation:
    current_generation: int
    current: CompleteBundleRef
    pending_intent_sha256: str | None = None
    staged: CompleteBundleRef | None = None
    independent_bundle_readback_sha256: str | None = None

    def __post_init__(self) -> None:
        if (type(self.current_generation) is not int or self.current_generation < 0
                or not isinstance(self.current, CompleteBundleRef)
                or (self.staged is not None and not isinstance(self.staged, CompleteBundleRef))):
            raise ValueError("CUTOVER_INVALID_OBSERVATION")
        for value in (self.pending_intent_sha256, self.independent_bundle_readback_sha256):
            if value is not None:
                require_sha256(value)


@dataclass(frozen=True)
class DisposableCutoverPlan:
    intent_sha256: str
    status: CutoverPlanStatus
    actions: tuple[CutoverAction, ...]
    blockers: tuple[str, ...]
    training_authorized: bool = field(default=False, init=False)


def plan_disposable_cutover(intent: CutoverIntent,
                            observed: CutoverObservation) -> DisposableCutoverPlan:
    """Describe crash/retry obligations without accepting self-reported proof.

    Even a complete supplied observation yields no admission or neural action.
    The independent readback reference is itself unqualified until the future
    executor consumes authentic pinned evidence through existing owners.
    """
    identity = intent.identity
    blockers = []
    if observed.pending_intent_sha256 not in (None, identity):
        blockers.append("OTHER_CUTOVER_INTENT_PRESENT")
    if (observed.current_generation == intent.parent_generation + 1
            and observed.staged is not None and observed.current == observed.staged):
        if (observed.current.catalog_sha256 != intent.successor_catalog_sha256
                or observed.current.vocabulary_size != intent.successor_vocabulary_size
                or observed.current.optimizer_step != intent.parent.optimizer_step
                or observed.pending_intent_sha256 != identity
                or observed.independent_bundle_readback_sha256 is None):
            blockers.append("COMMITTED_CUTOVER_LINEAGE_INCOMPLETE")
        if blockers:
            return DisposableCutoverPlan(identity, CutoverPlanStatus.BLOCKED, (), tuple(blockers))
        return DisposableCutoverPlan(
            identity, CutoverPlanStatus.OBSERVED_COMMIT_REQUIRES_EVENT_READBACK,
            (CutoverAction.VERIFY_INDEPENDENT_ADMISSION,
             CutoverAction.READ_BACK_COMPLETE_BUNDLE, CutoverAction.REPLAY_COMMITTED_EVENTS),
            ("EXECUTOR_AND_CRASH_PROOFS_NOT_IMPLEMENTED",))
    if observed.current_generation != intent.parent_generation or observed.current != intent.parent:
        blockers.append("PARENT_GENERATION_OR_BUNDLE_DRIFT")
    if observed.staged is not None:
        if (observed.staged.catalog_sha256 != intent.successor_catalog_sha256
                or observed.staged.vocabulary_size != intent.successor_vocabulary_size
                or observed.staged.optimizer_step != intent.parent.optimizer_step
                or observed.pending_intent_sha256 != identity):
            blockers.append("STAGED_BUNDLE_INTENT_DRIFT")
    elif observed.independent_bundle_readback_sha256 is not None:
        blockers.append("READBACK_WITHOUT_STAGED_BUNDLE")
    if observed.independent_bundle_readback_sha256 is not None:
        require_sha256(observed.independent_bundle_readback_sha256)
    if blockers:
        return DisposableCutoverPlan(identity, CutoverPlanStatus.BLOCKED, (), tuple(blockers))
    actions = [CutoverAction.VERIFY_INDEPENDENT_ADMISSION,
               CutoverAction.VERIFY_APPEND_ONLY_CATALOG, CutoverAction.VERIFY_DISK_RESERVE]
    if observed.staged is None:
        actions.extend((CutoverAction.ALLOCATE_DISPOSABLE_MODEL_AND_OWN_ADAMW,
                        CutoverAction.STAGE_NEW_COMPLETE_BUNDLE))
    # Always reread a staged bundle. A caller-supplied digest is no I/O proof.
    actions.extend((CutoverAction.READ_BACK_COMPLETE_BUNDLE,
                    CutoverAction.COMMIT_GENERATION_WITH_EXISTING_OUTBOX,
                    CutoverAction.REPLAY_COMMITTED_EVENTS))
    return DisposableCutoverPlan(identity, CutoverPlanStatus.DRAFT_EXECUTOR_REQUIRED,
                                tuple(actions), ("EXECUTOR_AND_CRASH_PROOFS_NOT_IMPLEMENTED",))
