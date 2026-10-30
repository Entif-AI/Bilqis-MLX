"""Manifest for the existing atlas engram contract."""
from __future__ import annotations
from .contracts import INITIAL_MOTIF_CAPACITY, MOTIF_VECTOR_WIDTH

from dataclasses import asdict
from dataclasses import dataclass
from .contracts import (
    MANIFEST_SCHEMA, MAX_CANDIDATE_ALLOCATIONS, MAX_MOTIF_CAPACITY, MOTIF_PAGE_STATE_BYTES, MotifKey,
    MotifSlot, PAGE_GROWTH_SCHEMA, PLAN_SCHEMA, VIEW_SCHEMA, _SHA,
    _bucket, _digest, _invalid,
)


@dataclass(frozen=True)
class MotifManifest:
    semantic_release: str
    slots: tuple[MotifSlot, ...] = ()
    capacity: int = INITIAL_MOTIF_CAPACITY
    schema_version: str = MANIFEST_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.slots, tuple)
                or any(type(item) is not MotifSlot for item in self.slots)):
            _invalid("BAMF_MOTIF_MANIFEST_INVALID")
        indices = tuple(item.slot_id for item in self.slots)
        if (not _SHA.fullmatch(self.semantic_release)
                or type(self.capacity) is not int
                or not INITIAL_MOTIF_CAPACITY <= self.capacity <= MAX_MOTIF_CAPACITY
                or self.capacity % INITIAL_MOTIF_CAPACITY
                or indices != tuple(range(len(self.slots)))
                or len({item.key for item in self.slots}) != len(self.slots)
                or len(self.slots) > self.capacity
                or any(item.key.semantic_release != self.semantic_release
                       for item in self.slots)
                or self.schema_version != MANIFEST_SCHEMA):
            _invalid("BAMF_MOTIF_MANIFEST_INVALID")

    @property
    def digest(self) -> str:
        return _digest(asdict(self))

    def lookup(self, key: MotifKey) -> int | None:
        if key.semantic_release != self.semantic_release:
            _invalid("BAMF_MOTIF_FOREIGN_RELEASE")
        bucket = _bucket(key)
        for item in self.slots:
            if _bucket(item.key) == bucket and item.key == key:
                return item.slot_id
        return None


@dataclass(frozen=True)
class MotifBudget:
    new_slot_limit: int = MAX_CANDIDATE_ALLOCATIONS
    page_growth_bytes: int = 0

    def __post_init__(self) -> None:
        if (type(self.new_slot_limit) is not int
                or not 0 <= self.new_slot_limit <= MAX_CANDIDATE_ALLOCATIONS
                or type(self.page_growth_bytes) is not int
                or self.page_growth_bytes < 0):
            _invalid("BAMF_MOTIF_BUDGET_INVALID")


@dataclass(frozen=True)
class MotifAllocationPlan:
    parent_manifest_digest: str
    allocated: tuple[MotifSlot, ...]
    pending: tuple[MotifKey, ...]
    observed_uses: tuple[tuple[str, int], ...]
    schema_version: str = PLAN_SCHEMA


@dataclass(frozen=True)
class MotifMatch:
    occurrence_id: str
    exact_key_digest: str
    structural_key_digest: str
    disposition: str
    slot_id: int | None


@dataclass(frozen=True)
class MotifPageGrowth:
    parent_capacity: int
    candidate_capacity: int
    added_pages: int
    reserved_state_bytes: int
    declared_budget_bytes: int
    schema_version: str = PAGE_GROWTH_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.parent_capacity) is not int
                or type(self.candidate_capacity) is not int
                or type(self.added_pages) is not int
                or type(self.reserved_state_bytes) is not int
                or type(self.declared_budget_bytes) is not int
                or self.declared_budget_bytes < 0
                or not INITIAL_MOTIF_CAPACITY <= self.parent_capacity <= MAX_MOTIF_CAPACITY
                or self.parent_capacity % INITIAL_MOTIF_CAPACITY
                or self.added_pages not in (0, 1)
                or self.candidate_capacity != (
                    self.parent_capacity + self.added_pages * INITIAL_MOTIF_CAPACITY)
                or self.candidate_capacity > MAX_MOTIF_CAPACITY
                or self.reserved_state_bytes != self.added_pages * MOTIF_PAGE_STATE_BYTES
                or self.reserved_state_bytes > self.declared_budget_bytes
                or self.schema_version != PAGE_GROWTH_SCHEMA):
            _invalid("BAMF_MOTIF_PAGE_GROWTH_INVALID")


@dataclass(frozen=True)
class CandidateMotifView:
    matches: tuple[MotifMatch, ...]
    plan: MotifAllocationPlan
    page_growth: MotifPageGrowth
    schema_version: str = VIEW_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.matches) is not tuple
                or any(type(item) is not MotifMatch for item in self.matches)
                or type(self.plan) is not MotifAllocationPlan
                or type(self.page_growth) is not MotifPageGrowth
                or self.schema_version != VIEW_SCHEMA):
            _invalid("BAMF_MOTIF_CANDIDATE_VIEW_INVALID")


def _plan_page_growth(
    parent_capacity: int, occupied: int, requested: int, budget_bytes: int,
) -> MotifPageGrowth:
    if (type(parent_capacity) is not int
            or not INITIAL_MOTIF_CAPACITY <= parent_capacity <= MAX_MOTIF_CAPACITY
            or parent_capacity % INITIAL_MOTIF_CAPACITY
            or type(occupied) is not int or not 0 <= occupied <= parent_capacity
            or type(requested) is not int or requested < 0
            or type(budget_bytes) is not int or budget_bytes < 0):
        _invalid("BAMF_MOTIF_PAGE_GROWTH_INVALID")
    add_page = (
        requested > parent_capacity - occupied
        and parent_capacity < MAX_MOTIF_CAPACITY
        and budget_bytes >= MOTIF_PAGE_STATE_BYTES
    )
    return MotifPageGrowth(
        parent_capacity,
        parent_capacity + (INITIAL_MOTIF_CAPACITY if add_page else 0),
        int(add_page),
        MOTIF_PAGE_STATE_BYTES if add_page else 0,
        budget_bytes,
    )
