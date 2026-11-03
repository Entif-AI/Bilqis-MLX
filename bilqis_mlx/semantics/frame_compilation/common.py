"""Compiler schemas and shared source contracts.

Incomplete frames remain raw source-visible atoms. A complete frame becomes
a packed closure only at its causal boundary, after A13 context re-approval.
No assessment labels, future source suffix or mutable cache state is consumed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from enum import Enum

import re

from bilqis_mlx.errors import ErrorBus, SEMANTIC_FRAME

from bilqis_mlx.semantics.context_eligibility import (
    ApprovedContextProjection, ContextHold, ContextPolicy,
    SourceFrontier, SourceGrant, TaskScope, project_context,
)

from bilqis_mlx.semantics.domains import contract_digest

from bilqis_mlx.semantics.frame_codec import (
    PackDisposition, PackedFrame, SchemaTagMap, _canonical_bytes,
    pack_frame, unpack_frame,
)

from bilqis_mlx.semantics.frame_schema import (
    AtomicFrame, FrameInstance, FrameSchema, FrameTree, SourceSpan,
    validate_frame_tree,
)

SOURCE_AST_SCHEMA = "bilqis.streaming-source-ast/v1"

SOURCE_ATOM_SCHEMA = "bilqis.streaming-source-atom/v1"

COMPILER_CONFIG_SCHEMA = "bilqis.frame-compiler-config/v1"

COMPILED_POSITION_SCHEMA = "bilqis.compiled-prefix-position/v1"

COMPILED_BATCH_SCHEMA = "bilqis.compiled-frame-batch/v2"

VISIBLE_AST_SCHEMA = "bilqis.visible-source-ast/v1"

PREFIX_MAPS_SCHEMA = "bilqis.compiled-prefix-maps/v1"

COMPILED_ROWS_SCHEMA = "bilqis.compiled-frame-rows/v1"

TRAINING_EXAMPLE_SCHEMA = "bilqis.compiled-training-example/v1"

HIDDEN_TARGET_SCHEMA = "bilqis.hidden-answer-targets/v1"

LAWFUL_SEGMENT_SCHEMA = "bilqis.lawful-source-segment/v1"

COMPILED_SEGMENTS_SCHEMA = "bilqis.compiled-frame-segments/v1"

BOUNDARY_EVIDENCE_SCHEMA = "bilqis.source-segment-boundary/v1"

ATOM_EVIDENCE_SCHEMA = "bilqis.source-atom-evidence/v1"

MAX_NEURAL_POSITIONS = 1024

POLICY_VERSION_ARITY = 4

ROW_COMPILER_INPUT_ARITY = 3

_SHA = re.compile(r"[0-9a-f]{64}\Z")

def _invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<prefix-compiler>",
        span_start=0, span_end=0,
    )

def _invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<prefix-compiler>",
        span_start=0, span_end=0,
    )
