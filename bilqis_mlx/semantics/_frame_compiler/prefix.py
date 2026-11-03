"""Prefix for causal source-prefix compilation."""
from __future__ import annotations
from .. import frame_compiler as _facade
from ..frame_schema import FrameInstance
from .approval import _approved_occurrences, _approve_visible_frames
from .batch import CompiledFrameBatch
from .contracts import MAX_NEURAL_POSITIONS
from .positions import PositionKind, CompiledPosition
from .source import StreamingAST, FrameCompilerConfig



def _pack_closures(closed, approved_by_occurrence, compiler_config):
    from .. import frame_compiler

    schemas = {
        (schema.schema_id, schema.revision): schema
        for schema in compiler_config.schemas
    }
    closures = {}
    for frame in closed:
        envelope = approved_by_occurrence[frame.occurrence_id]
        schema = (
            schemas.get((frame.frame_schema_id, frame.frame_schema_revision))
            if isinstance(frame, FrameInstance) else None)
        if isinstance(frame, FrameInstance) and schema is None:
            _facade._invalid("BAMF_PREFIX_SCHEMA_NOT_RELEASED")
        packed = frame_compiler.pack_frame(
            frame, schema=schema, schema_map=compiler_config.schema_map)
        closing_index = _facade._closure_end(frame, approved_by_occurrence) - 1
        closures.setdefault(closing_index, []).append(
            CompiledPosition(
                closing_index, PositionKind.CLOSURE,
                packed=packed, frame_handle=envelope.frame_handle))
    return closures


def compile_prefix(
    ast: StreamingAST,
    visible_end: int,
    release: str,
    compiler_config: FrameCompilerConfig,
) -> CompiledFrameBatch:
    """Append source atoms and newly closed, re-approved packed frames."""
    if (not isinstance(ast, StreamingAST)
            or not isinstance(compiler_config, FrameCompilerConfig)
            or type(visible_end) is not int
            or not 0 <= visible_end <= len(ast.atoms)
            or visible_end > compiler_config.task.causal_prefix_end
            or release != compiler_config.task.semantic_release
            or release != compiler_config.schema_map.semantic_release):
        _facade._invalid("BAMF_PREFIX_COMPILE_INPUT_INVALID")

    approved_by_occurrence, duplicates = _approved_occurrences(compiler_config)
    closed = _facade._source_frames(
        ast, visible_end, approved_by_occurrence)
    # Preflight before packing frames, allocating model positions or padding.
    # No silent truncation is permitted at this boundary.
    if visible_end + len(closed) > MAX_NEURAL_POSITIONS:
        _facade._invalid("BAMF_PREFIX_NEURAL_LENGTH_EXCEEDED")
    context_digest = _approve_visible_frames(
        ast, visible_end, release, compiler_config, closed,
        approved_by_occurrence, duplicates)
    closures = _pack_closures(closed, approved_by_occurrence, compiler_config)
    positions = []
    for atom in ast.atoms[:visible_end]:
        positions.append(CompiledPosition(
            atom.index, PositionKind.ATOM, atom=atom))
        positions.extend(closures.get(atom.index, ()))
    positions = tuple(positions)
    policy_version = (
        compiler_config.policy.policy_id,
        compiler_config.policy.policy_epoch,
        compiler_config.policy.rights_epoch,
        compiler_config.frontier.correction_generation)
    return CompiledFrameBatch(
        ast.source_instance_id, release, visible_end, positions,
        compiler_config.schema_map, context_digest,
        compiler_config.task.scope, policy_version,
        _facade._prefix_digest(
            ast.source_instance_id, release, visible_end,
            compiler_config.schema_map, context_digest, positions,
            compiler_config.task.scope, policy_version))
