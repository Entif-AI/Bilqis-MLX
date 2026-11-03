"""Stable public surface for the causal frame compiler."""
from .frame_compilation.common import (
    ATOM_EVIDENCE_SCHEMA, ApprovedContextProjection, AtomicFrame, BOUNDARY_EVIDENCE_SCHEMA, COMPILED_BATCH_SCHEMA, COMPILED_POSITION_SCHEMA, COMPILED_ROWS_SCHEMA, COMPILED_SEGMENTS_SCHEMA, COMPILER_CONFIG_SCHEMA, ContextHold, ContextPolicy, Enum, ErrorBus, FrameInstance, FrameSchema, FrameTree, HIDDEN_TARGET_SCHEMA, LAWFUL_SEGMENT_SCHEMA, MAX_NEURAL_POSITIONS, POLICY_VERSION_ARITY, PREFIX_MAPS_SCHEMA, PackDisposition, PackedFrame, ROW_COMPILER_INPUT_ARITY, SEMANTIC_FRAME, SOURCE_AST_SCHEMA, SOURCE_ATOM_SCHEMA, SchemaTagMap, SourceFrontier, SourceGrant, SourceSpan, TRAINING_EXAMPLE_SCHEMA, TaskScope, VISIBLE_AST_SCHEMA, _SHA, _canonical_bytes, _invalid, asdict, contract_digest, dataclass, pack_frame, project_context, re, replace, unpack_frame, validate_frame_tree
)
from .frame_compilation.source import (SourceAtom, StreamingAST, FrameCompilerConfig, atom_evidence_digest, _grant_allows, _segment_authority)
from .frame_compilation.positions import (PositionKind, CompiledPosition, _prefix_digest, _canonical_position_order, CompiledFrameBatch, CompileStats, _compile_stats)
from .frame_compilation.maps import (SourcePosition, ScopeBoundary, RoleAccess, ExpansionHandle, PrefixMaps, _derive_maps)
from .frame_compilation.prefix import (VisibleAST, _closure_end, _source_frames, compile_prefix)
from .frame_compilation.training import (CompiledFrameRows, HiddenAnswerTargets, CompiledTrainingExample, compile_training_example, compile_prefix_rows)
from .frame_compilation.segments import (LawfulSourceSegment, boundary_evidence_digest, CompiledFrameSegments, compile_lawful_segments)
from .frame_compilation.reconstruction import (reconstruct, validate_partial_visible_forest)

for _public_object in (
    _invalid, atom_evidence_digest, SourceAtom, StreamingAST, FrameCompilerConfig, _grant_allows, _segment_authority, PositionKind, CompiledPosition, _prefix_digest, _canonical_position_order, CompiledFrameBatch, CompileStats, _compile_stats, SourcePosition, ScopeBoundary, RoleAccess, ExpansionHandle, PrefixMaps, _derive_maps, VisibleAST, _closure_end, _source_frames, compile_prefix, CompiledFrameRows, HiddenAnswerTargets, CompiledTrainingExample, compile_training_example, LawfulSourceSegment, boundary_evidence_digest, CompiledFrameSegments, compile_lawful_segments, compile_prefix_rows, reconstruct, validate_partial_visible_forest
):
    _public_object.__module__ = __name__
del _public_object
