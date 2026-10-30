"""Stable atlas engram API with cohesive implementation owners."""
from __future__ import annotations
from .contracts import INITIAL_MOTIF_CAPACITY, MOTIF_VECTOR_WIDTH
from collections import Counter
from dataclasses import asdict
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Protocol
from bilqis_mlx.errors import ErrorBus
from bilqis_mlx.errors import SCHOOL
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents
from bilqis_mlx.runtime.model_topology_v2 import Initializer
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.runtime.model_topology_v2 import MOTIF_PAGE_SHAPE
from bilqis_mlx.runtime.model_topology_v2 import expected_bamf_shapes
from bilqis_mlx.runtime.model_topology_v2 import initialize_bamf_row
from .contracts import (
    KEY_SCHEMA, MEMBER_SCHEMA, MANIFEST_SCHEMA, PLAN_SCHEMA, VIEW_SCHEMA,
    PAGE_GROWTH_SCHEMA, FRAME_INPUT_SCHEMA, FRAME_INSTANCE_SCHEMA, FRAME_SCHEMA, CONCEPT_SCHEMA,
    CHILD_SCHEMA, MAX_CANDIDATE_ALLOCATIONS, OBSERVED_USE_ARITY, MAX_MOTIF_CAPACITY, MOTIF_PAGE_STATE_BYTES,
    _SHA, _STATES, _invalid, _bytes, _digest,
    FrameInstanceV2, FrameSchemaV1, MotifFrameInput, MotifMember, MotifKey,
    MotifSlot, _bucket,
)
from .manifest import (
    MotifManifest, MotifBudget, MotifAllocationPlan, MotifMatch, MotifPageGrowth,
    CandidateMotifView, _plan_page_growth,
)
from .keys import (
    _state, _member, motif_keys,
)
from .allocation import (
    prepare_motifs, candidate_motif_manifest, initialize_planned_motif_slot,
)

for _export in (
    _invalid, _bytes, _digest, FrameInstanceV2, FrameSchemaV1,
    MotifFrameInput, MotifMember, MotifKey, MotifSlot, _bucket,
    MotifManifest, MotifBudget, MotifAllocationPlan, MotifMatch, MotifPageGrowth,
    CandidateMotifView, _plan_page_growth, _state, _member, motif_keys,
    prepare_motifs, candidate_motif_manifest, initialize_planned_motif_slot,
):
    _export.__module__ = __name__
del _export
