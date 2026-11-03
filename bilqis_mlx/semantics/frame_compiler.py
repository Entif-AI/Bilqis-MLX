"""Causal, append-only prefix compiler for source-attested frame trees.

Incomplete frames remain raw source-visible atoms. A complete frame becomes
a packed closure only at its causal boundary, after A13 context re-approval.
No assessment labels, future source suffix or mutable cache state is consumed.
"""
from __future__ import annotations

from ._public_identity.module_identity import restore_public_module

from dataclasses import asdict, dataclass, replace
from enum import Enum
import re

from ..errors import ErrorBus, SEMANTIC_FRAME
from .context_eligibility import (
    ApprovedContextProjection, ContextHold, ContextPolicy,
    SourceFrontier, SourceGrant, TaskScope, project_context,
)
from .domains import contract_digest
from .frame_codec import (
    PackDisposition, PackedFrame, SchemaTagMap, _canonical_bytes,
    pack_frame, unpack_frame,
)
from .frame_schema import (
    AtomicFrame, FrameInstance, FrameSchema, FrameTree, SourceSpan,
    validate_frame_tree,
)


from ._frame_compiler.batch import (
    CompiledFrameBatch,
)
from ._frame_compiler.contracts import (
    SOURCE_AST_SCHEMA, SOURCE_ATOM_SCHEMA, COMPILER_CONFIG_SCHEMA,
    COMPILED_POSITION_SCHEMA, COMPILED_BATCH_SCHEMA, VISIBLE_AST_SCHEMA,
    PREFIX_MAPS_SCHEMA, COMPILED_ROWS_SCHEMA, TRAINING_EXAMPLE_SCHEMA,
    HIDDEN_TARGET_SCHEMA, LAWFUL_SEGMENT_SCHEMA, COMPILED_SEGMENTS_SCHEMA,
    BOUNDARY_EVIDENCE_SCHEMA, ATOM_EVIDENCE_SCHEMA, MAX_NEURAL_POSITIONS,
    POLICY_VERSION_ARITY, ROW_COMPILER_INPUT_ARITY, _SHA,
    _invalid,
)
from ._frame_compiler.map_derivation import _derive_maps
from ._frame_compiler.stats_accounting import _compile_stats
from ._frame_compiler.maps import (
    SourcePosition, ScopeBoundary, RoleAccess,
    ExpansionHandle, PrefixMaps,
)
from ._frame_compiler.positions import (
    PositionKind, CompiledPosition, _prefix_digest,
    _canonical_position_order,
)
from ._frame_compiler.prefix import (
    compile_prefix,
)
from ._frame_compiler.reconstruction import (
    reconstruct,
)
from ._frame_compiler.rows import (
    CompiledFrameRows, HiddenAnswerTargets, CompiledTrainingExample,
    compile_training_example, compile_prefix_rows,
)
from ._frame_compiler.segments import (
    LawfulSourceSegment, boundary_evidence_digest, CompiledFrameSegments,
    compile_lawful_segments,
)
from ._frame_compiler.source import (
    atom_evidence_digest, SourceAtom, StreamingAST,
    FrameCompilerConfig, _grant_allows, _segment_authority,
)
from ._frame_compiler.stats import (
    CompileStats,
)
from ._frame_compiler.visibility import (
    VisibleAST, _closure_end, _source_frames,
)


def validate_partial_visible_forest(
    compiled, source_ast, compiler_config, *, expected_receipt=None,
):
    """A05.4 compatibility entrypoint for source-owned partial-forest validation."""
    from .partial_visible_forest import validate_partial_visible_forest as validate

    return validate(
        compiled, source_ast, compiler_config,
        expected_receipt=expected_receipt)



# Preserve canonical identities for public compiler records and callables.
for _public in (
    _invalid, atom_evidence_digest, SourceAtom,
    StreamingAST, FrameCompilerConfig, _grant_allows,
    _segment_authority, PositionKind, CompiledPosition,
    _prefix_digest, _canonical_position_order, CompiledFrameBatch,
    CompileStats, SourcePosition,
    ScopeBoundary, RoleAccess, ExpansionHandle,
    PrefixMaps, _derive_maps, VisibleAST,
    _closure_end, _source_frames, compile_prefix,
    CompiledFrameRows, HiddenAnswerTargets, CompiledTrainingExample,
    compile_training_example, LawfulSourceSegment, boundary_evidence_digest,
    CompiledFrameSegments, compile_lawful_segments, compile_prefix_rows,
    reconstruct,
):
    restore_public_module(_public, __name__)
