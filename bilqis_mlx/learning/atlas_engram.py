"""Public B07 motif identity and candidate-planning facade.

The implementation is split by ownership seam so callers retain the historical
`bilqis_mlx.learning.atlas_engram` API without concentrating identity, key
derivation, allocation planning, and initialization in one oversized module.
"""
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


__all__ = [
    "CHILD_SCHEMA", "CONCEPT_SCHEMA", "FRAME_INPUT_SCHEMA",
    "FRAME_INSTANCE_SCHEMA", "FRAME_SCHEMA", "INITIAL_MOTIF_CAPACITY",
    "KEY_SCHEMA", "MANIFEST_SCHEMA", "MAX_CANDIDATE_ALLOCATIONS",
    "MAX_MOTIF_CAPACITY", "MEMBER_SCHEMA", "MOTIF_PAGE_STATE_BYTES",
    "MOTIF_VECTOR_WIDTH", "OBSERVED_USE_ARITY", "PAGE_GROWTH_SCHEMA",
    "PLAN_SCHEMA", "VIEW_SCHEMA", "FrameInstanceV2", "FrameSchemaV1",
    "MotifFrameInput", "MotifKey", "MotifManifest", "MotifMember",
    "MotifSlot", "CandidateMotifView", "MotifAllocationPlan", "MotifBudget",
    "MotifMatch", "MotifPageGrowth", "_plan_page_growth", "build_motif_input", "motif_keys",
    "prepare_motifs", "candidate_motif_manifest", "initialize_planned_motif_slot",
]
