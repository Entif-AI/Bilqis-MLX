"""Causal, append-only prefix compiler for source-attested frame trees.

Incomplete frames remain raw source-visible atoms. A complete frame becomes
a packed closure only at its causal boundary, after A13 context re-approval.
No assessment labels, future source suffix or mutable cache state is consumed.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import re

from ..errors import ErrorBus, SEMANTIC_FRAME
from .context_eligibility import (
    ApprovedContextProjection, ContextHold, ContextPolicy,
    SourceFrontier, TaskScope, project_context,
)
from .domains import contract_digest
from .frame_codec import PackedFrame, SchemaTagMap, pack_frame, unpack_frame
from .frame_schema import (
    AtomicFrame, FrameInstance, FrameSchema, FrameTree, validate_frame_tree,
)


SOURCE_AST_SCHEMA = "bilqis.streaming-source-ast/v1"
SOURCE_ATOM_SCHEMA = "bilqis.streaming-source-atom/v1"
COMPILER_CONFIG_SCHEMA = "bilqis.frame-compiler-config/v1"
COMPILED_POSITION_SCHEMA = "bilqis.compiled-prefix-position/v1"
COMPILED_BATCH_SCHEMA = "bilqis.compiled-frame-batch/v1"
VISIBLE_AST_SCHEMA = "bilqis.visible-source-ast/v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _invalid(reason: str) -> None:
    ErrorBus.raise_(
        SEMANTIC_FRAME.BINDING.INVALID,
        reason=reason, role_id="<prefix-compiler>",
        span_start=0, span_end=0,
    )


@dataclass(frozen=True)
class SourceAtom:
    """One already-source-visible token at its immutable stream position."""
    index: int
    token: str
    source_reference: str
    schema_version: str = SOURCE_ATOM_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.index) is not int or self.index < 0
                or not isinstance(self.token, str) or not self.token
                or not isinstance(self.source_reference, str)
                or not self.source_reference
                or self.schema_version != SOURCE_ATOM_SCHEMA):
            _invalid("BAMF_PREFIX_ATOM_INVALID")


@dataclass(frozen=True)
class StreamingAST:
    source_instance_id: str
    atoms: tuple[SourceAtom, ...]
    frames: tuple[FrameTree, ...]
    schema_version: str = SOURCE_AST_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.source_instance_id, str)
                or not self.source_instance_id
                or not isinstance(self.atoms, tuple)
                or tuple(atom.index for atom in self.atoms
                         if isinstance(atom, SourceAtom))
                != tuple(range(len(self.atoms)))
                or any(not isinstance(atom, SourceAtom) for atom in self.atoms)
                or not isinstance(self.frames, tuple)
                or any(not isinstance(tree, FrameTree) for tree in self.frames)
                or self.schema_version != SOURCE_AST_SCHEMA):
            _invalid("BAMF_PREFIX_SOURCE_AST_INVALID")


@dataclass(frozen=True)
class FrameCompilerConfig:
    schemas: tuple[FrameSchema, ...]
    schema_map: SchemaTagMap
    approved: ApprovedContextProjection | None
    task: TaskScope
    frontier: SourceFrontier
    policy: ContextPolicy
    schema_version: str = COMPILER_CONFIG_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.schemas, tuple)
                or any(not isinstance(item, FrameSchema)
                       for item in self.schemas)
                or len({item.identity for item in self.schemas})
                != len(self.schemas)
                or not isinstance(self.schema_map, SchemaTagMap)
                or (self.approved is not None
                    and not isinstance(self.approved, ApprovedContextProjection))
                or not isinstance(self.task, TaskScope)
                or not isinstance(self.frontier, SourceFrontier)
                or not isinstance(self.policy, ContextPolicy)
                or self.task.semantic_release != self.schema_map.semantic_release
                or self.schema_version != COMPILER_CONFIG_SCHEMA):
            _invalid("BAMF_PREFIX_CONFIG_INVALID")


class PositionKind(str, Enum):
    ATOM = "ATOM"
    CLOSURE = "CLOSURE"


@dataclass(frozen=True)
class CompiledPosition:
    source_index: int
    kind: PositionKind
    atom: SourceAtom | None = None
    packed: PackedFrame | None = None
    frame_handle: str | None = None
    schema_version: str = COMPILED_POSITION_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.source_index) is not int or self.source_index < 0
                or not isinstance(self.kind, PositionKind)
                or ((self.kind is PositionKind.ATOM)
                    != (self.atom is not None))
                or ((self.kind is PositionKind.CLOSURE)
                    != (self.packed is not None))
                or ((self.kind is PositionKind.CLOSURE)
                    != (self.frame_handle is not None))
                or (self.atom is not None
                    and (not isinstance(self.atom, SourceAtom)
                         or self.atom.index != self.source_index))
                or (self.packed is not None
                    and not isinstance(self.packed, PackedFrame))
                or (self.frame_handle is not None
                    and (not isinstance(self.frame_handle, str)
                         or not self.frame_handle))
                or self.schema_version != COMPILED_POSITION_SCHEMA):
            _invalid("BAMF_PREFIX_POSITION_INVALID")

    @property
    def cache_identity(self) -> tuple:
        if self.kind is PositionKind.ATOM:
            return (self.source_index, "ATOM", self.atom.token,
                    self.atom.source_reference)
        return (self.source_index, "CLOSURE", self.frame_handle,
                self.packed.projection_sha256, self.packed.sidecar.digest)


def _prefix_digest(
    source_id: str, release: str, visible_end: int,
    schema_map: SchemaTagMap, context_digest: str | None,
    positions: tuple[CompiledPosition, ...],
) -> str:
    return contract_digest((
        COMPILED_BATCH_SCHEMA, source_id, release, visible_end,
        schema_map.digest, context_digest,
        tuple(item.cache_identity for item in positions),
    ))


@dataclass(frozen=True)
class CompiledFrameBatch:
    source_instance_id: str
    semantic_release: str
    visible_end: int
    positions: tuple[CompiledPosition, ...]
    schema_map: SchemaTagMap
    context_digest: str | None
    cache_key: str
    schema_version: str = COMPILED_BATCH_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.source_instance_id, str)
                or not self.source_instance_id
                or not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or type(self.visible_end) is not int or self.visible_end < 0
                or not isinstance(self.positions, tuple)
                or any(not isinstance(item, CompiledPosition)
                       or item.source_index >= self.visible_end
                       for item in self.positions)
                or not isinstance(self.schema_map, SchemaTagMap)
                or self.schema_map.semantic_release != self.semantic_release
                or (self.context_digest is not None
                    and (not isinstance(self.context_digest, str)
                         or not _SHA.fullmatch(self.context_digest)))
                or not isinstance(self.cache_key, str)
                or self.cache_key != _prefix_digest(
                    self.source_instance_id, self.semantic_release,
                    self.visible_end, self.schema_map,
                    self.context_digest, self.positions)
                or self.schema_version != COMPILED_BATCH_SCHEMA):
            _invalid("BAMF_PREFIX_BATCH_INVALID")


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
    if (not isinstance(ast, StreamingAST)
            or not isinstance(compiler_config, FrameCompilerConfig)
            or type(visible_end) is not int
            or not 0 <= visible_end <= len(ast.atoms)
            or visible_end > compiler_config.task.causal_prefix_end
            or release != compiler_config.task.semantic_release
            or release != compiler_config.schema_map.semantic_release):
        _invalid("BAMF_PREFIX_COMPILE_INPUT_INVALID")

    approved_by_occurrence = (
        {envelope.frame.occurrence_id: envelope
         for envelope in compiler_config.approved.envelopes}
        if compiler_config.approved is not None else {})
    closed = _source_frames(
        ast, visible_end, approved_by_occurrence)
    envelopes = []
    for frame in closed:
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
        if {item.frame_handle for item in projected.eligible.frames} != {
                item.frame_handle for item in envelopes}:
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
    return CompiledFrameBatch(
        ast.source_instance_id, release, visible_end, positions,
        compiler_config.schema_map, context_digest,
        _prefix_digest(
            ast.source_instance_id, release, visible_end,
            compiler_config.schema_map, context_digest, positions))


def reconstruct(compiled: CompiledFrameBatch) -> VisibleAST:
    """Reconstruct exactly the source atoms and frame forest visible at p."""
    if not isinstance(compiled, CompiledFrameBatch):
        _invalid("BAMF_PREFIX_RECONSTRUCT_INPUT_INVALID")
    compiled.__post_init__()
    if (any(item.kind is PositionKind.CLOSURE
            for item in compiled.positions)
            and compiled.context_digest is None):
        _invalid("BAMF_PREFIX_CLOSURE_AUTHORITY_MISSING")
    atoms = []
    frames = []
    seen = set()
    last_index = -1
    for position in compiled.positions:
        if position.source_index < last_index:
            _invalid("BAMF_PREFIX_POSITION_ORDER_INVALID")
        last_index = position.source_index
        if position.kind is PositionKind.ATOM:
            if position.source_index != len(atoms):
                _invalid("BAMF_PREFIX_ATOM_ORDER_INVALID")
            atoms.append(position.atom)
            continue
        if (not atoms or position.source_index != atoms[-1].index):
            _invalid("BAMF_PREFIX_CLOSURE_ORDER_INVALID")
        frame = unpack_frame(
            position.packed, schema_map=compiled.schema_map)
        if (frame.occurrence_id in seen
                or frame.source_instance_id != compiled.source_instance_id
                or frame.causal_prefix_end > position.source_index + 1):
            _invalid("BAMF_PREFIX_CLOSURE_SOURCE_INVALID")
        seen.add(frame.occurrence_id)
        frames.append(frame)
    if len(atoms) != compiled.visible_end:
        _invalid("BAMF_PREFIX_ATOM_COUNT_INVALID")

    by_id = {frame.occurrence_id: frame for frame in frames}
    closing_order = {
        frame.occurrence_id: index for index, frame in enumerate(frames)}
    for frame in frames:
        if (frame.parent_occurrence_id in by_id
                and closing_order[frame.parent_occurrence_id]
                <= closing_order[frame.occurrence_id]):
            _invalid("BAMF_PREFIX_CHILD_CLOSURE_ORDER_INVALID")

    visiting = set()
    visited = set()

    def build(frame: FrameInstance | AtomicFrame) -> FrameTree:
        if frame.occurrence_id in visiting or frame.occurrence_id in visited:
            _invalid("BAMF_PREFIX_FRAME_TREE_CYCLE")
        visiting.add(frame.occurrence_id)
        children = tuple(
            build(child) for child in frames
            if child.parent_occurrence_id == frame.occurrence_id)
        tree = FrameTree(frame, children)
        validate_frame_tree(tree)
        visiting.remove(frame.occurrence_id)
        visited.add(frame.occurrence_id)
        return tree

    roots = tuple(
        build(frame) for frame in frames
        if frame.parent_occurrence_id not in by_id)
    if len(visited) != len(frames):
        _invalid("BAMF_PREFIX_FRAME_TREE_UNREACHABLE")
    return VisibleAST(
        compiled.source_instance_id, compiled.visible_end,
        tuple(atoms), roots)
