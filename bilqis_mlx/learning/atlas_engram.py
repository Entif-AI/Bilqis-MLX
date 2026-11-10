"""Public B07 motif identity and candidate-planning facade.

The implementation is split by ownership seam so callers retain the historical
`bilqis_mlx.learning.atlas_engram` API without concentrating identity, key
derivation, allocation planning, and initialization in one oversized module.
"""
from dataclasses import dataclass

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning._engram.atlas_engram_identity import (
    CHILD_SCHEMA,
    CONCEPT_SCHEMA,
    FRAME_INPUT_SCHEMA,
    FRAME_INSTANCE_SCHEMA,
    FRAME_SCHEMA,
    INITIAL_MOTIF_CAPACITY,
    KEY_SCHEMA,
    MANIFEST_SCHEMA,
    MAX_CANDIDATE_ALLOCATIONS,
    MAX_MOTIF_CAPACITY,
    MEMBER_SCHEMA,
    MOTIF_PAGE_STATE_BYTES,
    MOTIF_VECTOR_WIDTH,
    OBSERVED_USE_ARITY,
    FrameInstanceV2,
    FrameSchemaV1,
    MotifFrameInput,
    MotifKey,
    MotifManifest,
    MotifMember,
    MotifSlot,
)
from bilqis_mlx.learning._engram.atlas_engram_keys import build_motif_input, motif_keys
from bilqis_mlx.learning._engram.atlas_engram_plan_types import (
    PAGE_GROWTH_SCHEMA,
    PLAN_SCHEMA,
    VIEW_SCHEMA,
    CandidateMotifView,
    MotifAllocationPlan,
    MotifBudget,
    MotifMatch,
    MotifPageGrowth,
)
from bilqis_mlx.learning._engram.atlas_engram_planning import (
    _plan_page_growth,
    candidate_motif_manifest,
    initialize_planned_motif_slot,
    prepare_motifs,
)


MOTIF_READ_REPORT_SCHEMA = "bilqis.mlx.motif-read-report/v1"
MOTIF_READ_SITE_COUNT = 2
_PARTICIPATING_ROW_ARITY = 2


def _invalid_read_report() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


@dataclass(frozen=True)
class MotifReadReport:
    """Telemetry-only projection of one executed motif read.

    Rows are ``(page_index, row_index)`` coordinates in the persisted motif
    parameter pages.  The report never owns allocation, gradients, or custody.
    """

    site_index: int
    exact_count: int
    structural_count: int
    miss_count: int
    participating_rows: tuple[tuple[int, int], ...]
    schema_version: str = MOTIF_READ_REPORT_SCHEMA

    def __post_init__(self) -> None:
        if (
            type(self.site_index) is not int
            or not 0 <= self.site_index < MOTIF_READ_SITE_COUNT
            or any(
                type(value) is not int or value < 0
                for value in (
                    self.exact_count, self.structural_count, self.miss_count,
                )
            )
            or type(self.participating_rows) is not tuple
            or self.participating_rows != tuple(sorted(set(self.participating_rows)))
            or any(
                type(item) is not tuple
                or len(item) != _PARTICIPATING_ROW_ARITY
                or type(item[0]) is not int
                or type(item[1]) is not int
                or not 0 <= item[0] < MAX_MOTIF_CAPACITY // INITIAL_MOTIF_CAPACITY
                or not 0 <= item[1] < INITIAL_MOTIF_CAPACITY
                for item in self.participating_rows
            )
            or self.schema_version != MOTIF_READ_REPORT_SCHEMA
        ):
            _invalid_read_report()


def motif_read_report(site_index: int, result) -> MotifReadReport:
    """Report executed hit/miss counts without creating new neural state.

    HELD, foreign-release, and quarantined outcomes are non-reads and therefore
    count as misses here.  Their more specific status remains available on the
    source ``MotifReadResult`` for diagnostics and authority checks.
    """
    from bilqis_mlx.learning.atlas_engram_reads.records import MotifReadResult

    if (
        type(site_index) is not int
        or not 0 <= site_index < MOTIF_READ_SITE_COUNT
        or type(result) is not MotifReadResult
        or any(slot >= MAX_MOTIF_CAPACITY for slot in result.participating_slots)
    ):
        _invalid_read_report()
    dispositions = tuple(
        disposition
        for row in result.dispositions
        for disposition in row
    )
    exact = sum(disposition == "EXACT" for disposition in dispositions)
    structural = sum(disposition == "STRUCTURAL" for disposition in dispositions)
    participating_rows = tuple(
        (slot // INITIAL_MOTIF_CAPACITY, slot % INITIAL_MOTIF_CAPACITY)
        for slot in result.participating_slots
    )
    return MotifReadReport(
        site_index,
        exact,
        structural,
        len(dispositions) - exact - structural,
        participating_rows,
    )


__all__ = [
    "CHILD_SCHEMA", "CONCEPT_SCHEMA", "FRAME_INPUT_SCHEMA",
    "FRAME_INSTANCE_SCHEMA", "FRAME_SCHEMA", "INITIAL_MOTIF_CAPACITY",
    "KEY_SCHEMA", "MANIFEST_SCHEMA", "MAX_CANDIDATE_ALLOCATIONS",
    "MAX_MOTIF_CAPACITY", "MEMBER_SCHEMA", "MOTIF_PAGE_STATE_BYTES",
    "MOTIF_VECTOR_WIDTH", "OBSERVED_USE_ARITY", "PAGE_GROWTH_SCHEMA",
    "PLAN_SCHEMA", "VIEW_SCHEMA", "FrameInstanceV2", "FrameSchemaV1",
    "MotifFrameInput", "MotifKey", "MotifManifest", "MotifMember",
    "MotifSlot", "CandidateMotifView", "MotifAllocationPlan", "MotifBudget",
    "MotifMatch", "MotifPageGrowth", "MOTIF_READ_REPORT_SCHEMA",
    "MOTIF_READ_SITE_COUNT", "MotifReadReport", "motif_read_report",
    "_plan_page_growth", "build_motif_input", "motif_keys", "prepare_motifs",
    "candidate_motif_manifest", "initialize_planned_motif_slot",
]
