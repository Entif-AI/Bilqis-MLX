"""B07 candidate allocation and page-growth value objects."""
from dataclasses import dataclass

from bilqis_mlx.learning._engram.atlas_engram_identity import (
    INITIAL_MOTIF_CAPACITY,
    MAX_CANDIDATE_ALLOCATIONS,
    MAX_MOTIF_CAPACITY,
    MOTIF_PAGE_STATE_BYTES,
    MotifKey,
    MotifSlot,
    _invalid,
)


PLAN_SCHEMA = "bilqis.motif-allocation-plan/v1"
VIEW_SCHEMA = "bilqis.motif-candidate-view/v2"
PAGE_GROWTH_SCHEMA = "bilqis.motif-page-growth/v1"


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
