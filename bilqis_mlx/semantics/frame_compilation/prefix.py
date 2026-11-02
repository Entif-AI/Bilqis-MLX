"""Causal prefix validation and compilation."""
from __future__ import annotations
from .common import (AtomicFrame, ContextHold, FrameInstance, FrameTree, MAX_NEURAL_POSITIONS, VISIBLE_AST_SCHEMA, _invalid, dataclass, pack_frame, project_context, replace, validate_frame_tree)
from .source import (FrameCompilerConfig, SourceAtom, StreamingAST, _grant_allows, atom_evidence_digest)
from .positions import (CompiledFrameBatch, CompiledPosition, PositionKind, _prefix_digest)

@dataclass(frozen=True)
class VisibleAST:
    source_instance_id: str
    visible_end: int
    atoms: tuple[SourceAtom, ...]
    frames: tuple[FrameTree, ...]
    schema_version: str = VISIBLE_AST_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.source_instance_id, str)
                or not self.source_instance_id
                or type(self.visible_end) is not int
                or self.visible_end < 0
                or not isinstance(self.atoms, tuple)
                or tuple(atom.index for atom in self.atoms
                         if isinstance(atom, SourceAtom))
                != tuple(range(self.visible_end))
                or not isinstance(self.frames, tuple)
                or any(not isinstance(tree, FrameTree)
                       for tree in self.frames)
                or self.schema_version != VISIBLE_AST_SCHEMA):
            _invalid("BAMF_PREFIX_VISIBLE_AST_INVALID")


def _closure_end(
    frame: FrameInstance | AtomicFrame, approved_by_occurrence: dict,
) -> int:
    envelope = approved_by_occurrence.get(frame.occurrence_id)
    if envelope is None:
        return frame.causal_prefix_end
    return max(
        frame.causal_prefix_end, envelope.causal_prefix_end,
        *(member.visible_at_prefix for member in envelope.members))


def _source_frames(
    ast: StreamingAST, visible_end: int, approved_by_occurrence: dict,
) -> tuple[FrameInstance | AtomicFrame, ...]:
    ordered = []
    seen = set()

    def walk(tree: FrameTree) -> None:
        for child in sorted(
                tree.children,
                key=lambda item: (
                    item.root.source_span.start,
                    item.root.source_span.end,
                    item.root.occurrence_id)):
            walk(child)
        frame = tree.root
        if _closure_end(frame, approved_by_occurrence) > visible_end:
            return
        if any(_closure_end(child.root, approved_by_occurrence) > visible_end
               for child in tree.children):
            _invalid("BAMF_PREFIX_CHILD_FUTURE")
        # Future parent structure is never inspected or validated at p.
        validate_frame_tree(tree)
        if (frame.occurrence_id in seen
                or frame.source_instance_id != ast.source_instance_id
                or frame.causal_prefix_end > len(ast.atoms)
                or frame.causal_prefix_end == 0
                or frame.source_span.end > frame.causal_prefix_end):
            _invalid("BAMF_PREFIX_FRAME_SOURCE_INVALID")
        seen.add(frame.occurrence_id)
        ordered.append(frame)

    for tree in sorted(
            ast.frames,
            key=lambda item: (
                item.root.source_span.start,
                item.root.source_span.end,
                item.root.occurrence_id)):
        if (_closure_end(tree.root, approved_by_occurrence) <= visible_end
                and tree.root.parent_occurrence_id is not None):
            _invalid("BAMF_PREFIX_ROOT_PARENT_INVALID")
        walk(tree)
    return tuple(ordered)


def compile_prefix(
    ast: StreamingAST,
    visible_end: int,
    release: str,
    compiler_config: FrameCompilerConfig,
) -> CompiledFrameBatch:
    """Append source atoms and newly closed, re-approved packed frames."""
    from ..frame_compiler import pack_frame
    if (not isinstance(ast, StreamingAST)
            or not isinstance(compiler_config, FrameCompilerConfig)
            or type(visible_end) is not int
            or not 0 <= visible_end <= len(ast.atoms)
            or visible_end > compiler_config.task.causal_prefix_end
            or release != compiler_config.task.semantic_release
            or release != compiler_config.schema_map.semantic_release):
        _invalid("BAMF_PREFIX_COMPILE_INPUT_INVALID")

    approved_by_occurrence = {}
    duplicates = set()
    if compiler_config.approved is not None:
        for envelope in compiler_config.approved.envelopes:
            occurrence = envelope.frame.occurrence_id
            if occurrence in approved_by_occurrence:
                duplicates.add(occurrence)
            else:
                approved_by_occurrence[occurrence] = envelope
        for occurrence in duplicates:
            approved_by_occurrence[occurrence] = None
    closed = _source_frames(
        ast, visible_end, approved_by_occurrence)
    # Preflight before packing frames, allocating model positions or padding.
    # No silent truncation is permitted at this boundary.
    if visible_end + len(closed) > MAX_NEURAL_POSITIONS:
        _invalid("BAMF_PREFIX_NEURAL_LENGTH_EXCEEDED")
    grants = {
        grant.source_handle: grant
        for grant in compiler_config.frontier.grants}
    for atom in ast.atoms[:visible_end]:
        if not _grant_allows(
                grants.get(atom.source_reference),
                atom_evidence_digest(ast.source_instance_id, atom, release),
                compiler_config, release):
            _invalid("BAMF_PREFIX_ATOM_SOURCE_UNAUTHORIZED")
    envelopes = []
    for frame in closed:
        if frame.occurrence_id in duplicates:
            _invalid("BAMF_PREFIX_APPROVED_OCCURRENCE_DUPLICATE")
        envelope = approved_by_occurrence.get(frame.occurrence_id)
        if (envelope is None or envelope.frame != frame
                or envelope.causal_prefix_end != frame.causal_prefix_end):
            _invalid("BAMF_PREFIX_FRAME_NOT_APPROVED")
        envelopes.append(envelope)
    context_digest = None
    if envelopes:
        projected = project_context(
            tuple(envelopes),
            replace(compiler_config.task, causal_prefix_end=visible_end),
            compiler_config.frontier, compiler_config.policy)
        if isinstance(projected, ContextHold):
            _invalid("BAMF_PREFIX_CONTEXT_HELD")
        if (len(projected.eligible.frames) != len(envelopes)
                or {item.frame_handle for item in projected.eligible.frames} != {
                item.frame_handle for item in envelopes}):
            _invalid("BAMF_PREFIX_APPROVAL_DRIFT")
        context_digest = projected.digest

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
            _invalid("BAMF_PREFIX_SCHEMA_NOT_RELEASED")
        packed = pack_frame(
            frame, schema=schema, schema_map=compiler_config.schema_map)
        closing_index = _closure_end(frame, approved_by_occurrence) - 1
        closures.setdefault(closing_index, []).append(
            CompiledPosition(
                closing_index, PositionKind.CLOSURE,
                packed=packed, frame_handle=envelope.frame_handle))
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
        _prefix_digest(
            ast.source_instance_id, release, visible_end,
            compiler_config.schema_map, context_digest, positions,
            compiler_config.task.scope, policy_version))
