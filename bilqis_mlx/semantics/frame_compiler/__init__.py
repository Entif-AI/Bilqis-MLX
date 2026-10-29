"""Causal, append-only prefix compiler for source-attested frame trees.

Incomplete frames remain raw source-visible atoms. A complete frame becomes
a packed closure only at its causal boundary, after A13 context re-approval.
No assessment labels, future source suffix or mutable cache state is consumed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from enum import Enum
import re

from ...errors import ErrorBus, SEMANTIC_FRAME
from ..context_eligibility import (
    ApprovedContextProjection, ContextHold, ContextPolicy,
    SourceFrontier, SourceGrant, TaskScope, project_context,
)
from ..domains import contract_digest
from ..frame_codec import (
    PackDisposition, PackedFrame, SchemaTagMap, _canonical_bytes,
    pack_frame, unpack_frame,
)
from ..frame_schema import (
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


def atom_evidence_digest(
    source_instance_id: str, atom: "SourceAtom", release: str,
) -> str:
    """Bind one raw token to source-owned, prefix-stable rights evidence."""
    if (not isinstance(source_instance_id, str) or not source_instance_id
            or not isinstance(atom, SourceAtom)
            or not isinstance(release, str) or not _SHA.fullmatch(release)):
        _invalid("BAMF_PREFIX_ATOM_EVIDENCE_INVALID")
    return contract_digest((
        ATOM_EVIDENCE_SCHEMA, source_instance_id, release,
        atom.index, atom.token, atom.source_reference))


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


def _grant_allows(
    grant: SourceGrant | None, evidence_digest: str,
    config: FrameCompilerConfig, release: str,
) -> bool:
    task, policy, frontier = config.task, config.policy, config.frontier
    return (
        grant is not None and not grant.revoked
        and grant.evidence_digest == evidence_digest
        and grant.semantic_release == release
        and grant.principal_id == task.principal_id
        and grant.tenant_id == task.tenant_id
        and task.purpose in grant.permitted_purposes
        and task.jurisdiction in grant.permitted_jurisdictions
        and task.scope in grant.permitted_scopes
        and grant.source_regime in policy.allowed_regimes
        and task.purpose in policy.allowed_purposes
        and task.jurisdiction in policy.allowed_jurisdictions
        and task.scope in policy.allowed_scopes
        and grant.rights_epoch == frontier.rights_epoch
        and grant.rights_epoch == policy.rights_epoch
        and grant.correction_generation == frontier.correction_generation
        and grant.observed_at <= task.observed_frontier
        and grant.effective_from <= task.effective_time
        and (grant.effective_until is None
             or task.effective_time < grant.effective_until))


def _segment_authority(config: FrameCompilerConfig) -> tuple:
    task = config.task
    return (
        task.principal_id, task.tenant_id, task.purpose,
        task.jurisdiction, task.scope, task.semantic_release,
        task.observed_frontier, task.effective_time,
        config.policy, config.schema_map.digest,
        config.frontier.rights_epoch,
        config.frontier.correction_generation)


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
    scope: str, policy_version: tuple[str, int, int, int],
) -> str:
    return contract_digest((
        COMPILED_BATCH_SCHEMA, source_id, release, visible_end,
        schema_map.digest, context_digest, scope, policy_version,
        tuple(item.cache_identity for item in positions),
    ))


def _canonical_position_order(
    positions: tuple[CompiledPosition, ...], visible_end: int,
) -> bool:
    next_atom = 0
    last_source = -1
    for position in positions:
        if position.source_index < last_source:
            return False
        if position.kind is PositionKind.ATOM:
            if position.source_index != next_atom:
                return False
            next_atom += 1
        elif position.source_index >= next_atom:
            return False
        last_source = position.source_index
    return next_atom == visible_end


@dataclass(frozen=True)
class CompiledFrameBatch:
    source_instance_id: str
    semantic_release: str
    visible_end: int
    positions: tuple[CompiledPosition, ...]
    schema_map: SchemaTagMap
    context_digest: str | None
    scope: str
    policy_version: tuple[str, int, int, int]
    cache_key: str
    schema_version: str = COMPILED_BATCH_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.source_instance_id, str)
                or not self.source_instance_id
                or not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or type(self.visible_end) is not int or self.visible_end < 0
                or not isinstance(self.positions, tuple)
                or len(self.positions) > MAX_NEURAL_POSITIONS
                or any(not isinstance(item, CompiledPosition)
                       or item.source_index >= self.visible_end
                       for item in self.positions)
                or not _canonical_position_order(
                    self.positions, self.visible_end)
                or (self.context_digest is None
                    and any(item.kind is PositionKind.CLOSURE
                            for item in self.positions))
                or not isinstance(self.schema_map, SchemaTagMap)
                or self.schema_map.semantic_release != self.semantic_release
                or (self.context_digest is not None
                    and (not isinstance(self.context_digest, str)
                         or not _SHA.fullmatch(self.context_digest)))
                or not isinstance(self.scope, str) or not self.scope
                or not isinstance(self.policy_version, tuple)
                or len(self.policy_version) != POLICY_VERSION_ARITY
                or not isinstance(self.policy_version[0], str)
                or not self.policy_version[0]
                or any(type(epoch) is not int or epoch < 0
                       for epoch in self.policy_version[1:])
                or not isinstance(self.cache_key, str)
                or self.cache_key != _prefix_digest(
                    self.source_instance_id, self.semantic_release,
                    self.visible_end, self.schema_map,
                    self.context_digest, self.positions,
                    self.scope, self.policy_version)
                or self.schema_version != COMPILED_BATCH_SCHEMA):
            _invalid("BAMF_PREFIX_BATCH_INVALID")

    @property
    def maps(self) -> "PrefixMaps":
        return _derive_maps(self)

    @property
    def stats(self) -> "CompileStats":
        return _compile_stats(self)


@dataclass(frozen=True)
class CompileStats:
    actual_atoms: int
    actual_frames: int
    neural_positions: int
    disposition_shares: tuple[tuple[str, int, int], ...]
    sidecar_bytes: int

    def __post_init__(self) -> None:
        if (any(type(value) is not int or value < 0
                for value in (
                    self.actual_atoms, self.actual_frames,
                    self.neural_positions, self.sidecar_bytes))
                or self.actual_atoms + self.actual_frames
                != self.neural_positions
                or not isinstance(self.disposition_shares, tuple)
                or tuple(item[0] for item in self.disposition_shares)
                != ("COMPACT", "EXTENDED", "ATOMIC")
                or any(type(count) is not int or count < 0
                       or type(total) is not int
                       or total != self.actual_frames
                       for _, count, total in self.disposition_shares)
                or sum(count for _, count, _ in self.disposition_shares)
                != self.actual_frames):
            _invalid("BAMF_PREFIX_STATS_INVALID")


def _compile_stats(compiled: CompiledFrameBatch) -> CompileStats:
    closures = tuple(
        position.packed for position in compiled.positions
        if position.kind is PositionKind.CLOSURE)
    count = len(closures)
    shares = tuple(
        (disposition.name,
         sum(packed.disposition is disposition for packed in closures),
         count)
        for disposition in (
            PackDisposition.COMPACT,
            PackDisposition.EXTENDED,
            PackDisposition.ATOMIC))
    return CompileStats(
        len(compiled.positions) - count, count,
        len(compiled.positions), shares,
        sum(len(_canonical_bytes(asdict(packed.sidecar)))
            for packed in closures))


@dataclass(frozen=True)
class SourcePosition:
    position_index: int
    source_span: SourceSpan
    kind: PositionKind
    source_reference: str

    def __post_init__(self) -> None:
        if (type(self.position_index) is not int
                or self.position_index < 0
                or not isinstance(self.source_span, SourceSpan)
                or not isinstance(self.kind, PositionKind)
                or not isinstance(self.source_reference, str)
                or not self.source_reference):
            _invalid("BAMF_PREFIX_SOURCE_POSITION_INVALID")


@dataclass(frozen=True)
class ScopeBoundary:
    scope: str
    start_position: int
    end_position: int
    frame_handle: str | None

    def __post_init__(self) -> None:
        if (not isinstance(self.scope, str) or not self.scope
                or type(self.start_position) is not int
                or type(self.end_position) is not int
                or not 0 <= self.start_position <= self.end_position
                or (self.frame_handle is not None
                    and (not isinstance(self.frame_handle, str)
                         or not self.frame_handle))):
            _invalid("BAMF_PREFIX_SCOPE_BOUNDARY_INVALID")


@dataclass(frozen=True)
class RoleAccess:
    frame_handle: str
    position_index: int
    role_id: str
    occurrence_index: int
    state: str
    semantic_ids: tuple[str, ...]
    abi_indices: tuple[int, ...]
    source_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if (not isinstance(self.frame_handle, str)
                or not self.frame_handle
                or type(self.position_index) is not int
                or self.position_index < 0
                or not isinstance(self.role_id, str) or not self.role_id
                or type(self.occurrence_index) is not int
                or self.occurrence_index < 0
                or not isinstance(self.state, str) or not self.state
                or not isinstance(self.semantic_ids, tuple)
                or not isinstance(self.abi_indices, tuple)
                or not isinstance(self.source_references, tuple)
                or not (len(self.semantic_ids) == len(self.abi_indices)
                        == len(self.source_references))):
            _invalid("BAMF_PREFIX_ROLE_ACCESS_INVALID")


@dataclass(frozen=True)
class ExpansionHandle:
    frame_handle: str
    position_index: int
    occurrence_id: str
    content_digest: str
    projection_digest: str
    source_span: SourceSpan

    def __post_init__(self) -> None:
        if (not isinstance(self.frame_handle, str)
                or not self.frame_handle
                or type(self.position_index) is not int
                or self.position_index < 0
                or any(not isinstance(item, str)
                       or not _SHA.fullmatch(item)
                       for item in (
                           self.occurrence_id, self.content_digest,
                           self.projection_digest))
                or not isinstance(self.source_span, SourceSpan)):
            _invalid("BAMF_PREFIX_EXPANSION_HANDLE_INVALID")


@dataclass(frozen=True)
class PrefixMaps:
    position_to_source: tuple[SourcePosition, ...]
    source_to_positions: tuple[tuple[int, ...], ...]
    prefix_ends: tuple[int, ...]
    scope_boundaries: tuple[ScopeBoundary, ...]
    padding_mask: tuple[bool, ...]
    role_access: tuple[RoleAccess, ...]
    expansion_handles: tuple[ExpansionHandle, ...]
    schema_version: str = PREFIX_MAPS_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.position_to_source, tuple)
                or any(not isinstance(item, SourcePosition)
                       for item in self.position_to_source)
                or not isinstance(self.source_to_positions, tuple)
                or any(not isinstance(row, tuple)
                       or any(type(index) is not int or index < 0
                              for index in row)
                       for row in self.source_to_positions)
                or not isinstance(self.prefix_ends, tuple)
                or any(type(index) is not int or index < 0
                       for index in self.prefix_ends)
                or not isinstance(self.scope_boundaries, tuple)
                or any(not isinstance(item, ScopeBoundary)
                       for item in self.scope_boundaries)
                or not isinstance(self.padding_mask, tuple)
                or any(type(item) is not bool
                       for item in self.padding_mask)
                or len(self.padding_mask) != len(self.position_to_source)
                or not isinstance(self.role_access, tuple)
                or any(not isinstance(item, RoleAccess)
                       for item in self.role_access)
                or not isinstance(self.expansion_handles, tuple)
                or any(not isinstance(item, ExpansionHandle)
                       for item in self.expansion_handles)
                or self.schema_version != PREFIX_MAPS_SCHEMA):
            _invalid("BAMF_PREFIX_MAPS_INVALID")


def _derive_maps(compiled: CompiledFrameBatch) -> PrefixMaps:
    source_positions = []
    source_to_positions = [
        set() for _ in range(compiled.visible_end)]
    prefix_ends = [0] * (compiled.visible_end + 1)
    role_access = []
    expansion_handles = []
    boundaries = [ScopeBoundary(
        compiled.scope, 0, len(compiled.positions), None)]
    atom_positions = {}
    for position_index, position in enumerate(compiled.positions):
        source_index = position.source_index
        prefix_ends[source_index + 1] += 1
        if position.kind is PositionKind.ATOM:
            source_positions.append(SourcePosition(
                position_index, SourceSpan(source_index, source_index + 1),
                PositionKind.ATOM, position.atom.source_reference))
            source_to_positions[source_index].add(position_index)
            atom_positions[source_index] = position_index
            continue
        sidecar = position.packed.sidecar
        source_positions.append(SourcePosition(
            position_index, sidecar.source_span,
            PositionKind.CLOSURE, position.frame_handle))
        for index in range(
                sidecar.source_span.start,
                min(sidecar.source_span.end, compiled.visible_end)):
            source_to_positions[index].add(position_index)
        source_to_positions[source_index].add(position_index)
        expansion_handles.append(ExpansionHandle(
            position.frame_handle, position_index,
            sidecar.occurrence_id, sidecar.content_digest,
            position.packed.projection_sha256, sidecar.source_span))
        start = atom_positions.get(sidecar.source_span.start)
        if start is None:
            _invalid("BAMF_PREFIX_SCOPE_SOURCE_MISSING")
        boundaries.append(ScopeBoundary(
            sidecar.scope or compiled.scope,
            start, position_index + 1, position.frame_handle))
        for member in sidecar.constituents:
            role_access.append(RoleAccess(
                position.frame_handle, position_index,
                member.role_id, member.occurrence_index,
                member.state, member.semantic_ids,
                member.abi_indices, member.source_references))
    for index in range(1, len(prefix_ends)):
        prefix_ends[index] += prefix_ends[index - 1]
    return PrefixMaps(
        tuple(source_positions),
        tuple(tuple(sorted(indices)) for indices in source_to_positions),
        tuple(prefix_ends), tuple(boundaries),
        (True,) * len(compiled.positions),
        tuple(role_access), tuple(expansion_handles))


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


@dataclass(frozen=True)
class CompiledFrameRows:
    rows: tuple[CompiledFrameBatch, ...]
    padded_positions: tuple[tuple[CompiledPosition | None, ...], ...]
    padding_mask: tuple[tuple[bool, ...], ...]
    schema_version: str = COMPILED_ROWS_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.rows, tuple)
                or any(not isinstance(row, CompiledFrameBatch)
                       for row in self.rows)
                or not isinstance(self.padded_positions, tuple)
                or not isinstance(self.padding_mask, tuple)
                or len(self.rows) != len(self.padded_positions)
                or len(self.rows) != len(self.padding_mask)
                or self.schema_version != COMPILED_ROWS_SCHEMA):
            _invalid("BAMF_PREFIX_ROWS_INVALID")
        width = max((len(row.positions) for row in self.rows), default=0)
        for row, padded, mask in zip(
                self.rows, self.padded_positions, self.padding_mask):
            if (not isinstance(padded, tuple)
                    or not isinstance(mask, tuple)
                    or len(padded) != width or len(mask) != width
                    or padded[:len(row.positions)] != row.positions
                    or padded[len(row.positions):]
                    != (None,) * (width - len(row.positions))
                    or mask != (
                        (True,) * len(row.positions)
                        + (False,) * (width - len(row.positions)))):
                _invalid("BAMF_PREFIX_ROWS_PADDING_INVALID")


@dataclass(frozen=True)
class HiddenAnswerTargets:
    """Teacher-only target indices, never a member of CompiledFrameBatch."""
    source_instance_id: str
    target_indices: tuple[int, ...]
    target_mask: tuple[bool, ...]
    schema_version: str = HIDDEN_TARGET_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.source_instance_id, str)
                or not self.source_instance_id
                or not isinstance(self.target_indices, tuple)
                or len(self.target_indices) > MAX_NEURAL_POSITIONS
                or any(type(item) is not int or item < 0
                       for item in self.target_indices)
                or not isinstance(self.target_mask, tuple)
                or any(type(item) is not bool for item in self.target_mask)
                or len(self.target_indices) != len(self.target_mask)
                or self.schema_version != HIDDEN_TARGET_SCHEMA):
            _invalid("BAMF_PREFIX_TARGETS_INVALID")


@dataclass(frozen=True)
class CompiledTrainingExample:
    input_view: CompiledFrameBatch
    target_view: HiddenAnswerTargets
    schema_version: str = TRAINING_EXAMPLE_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.input_view, CompiledFrameBatch)
                or not isinstance(self.target_view, HiddenAnswerTargets)
                or self.input_view.source_instance_id
                != self.target_view.source_instance_id
                or self.schema_version != TRAINING_EXAMPLE_SCHEMA):
            _invalid("BAMF_PREFIX_TRAINING_EXAMPLE_INVALID")


def compile_training_example(
    ast: StreamingAST, targets: HiddenAnswerTargets,
    visible_end: int, release: str,
    config: FrameCompilerConfig,
) -> CompiledTrainingExample:
    """Keep hidden answer tensors outside the model-input/cache contract."""
    if (not isinstance(targets, HiddenAnswerTargets)
            or targets.source_instance_id != ast.source_instance_id):
        _invalid("BAMF_PREFIX_TARGET_SOURCE_MISMATCH")
    return CompiledTrainingExample(
        compile_prefix(ast, visible_end, release, config), targets)


@dataclass(frozen=True)
class LawfulSourceSegment:
    """Source-adapter-declared segment, not an arbitrary compiler cut."""
    origin_source_id: str
    global_span: SourceSpan
    boundary_source_handle: str
    ast: StreamingAST
    config: FrameCompilerConfig
    schema_version: str = LAWFUL_SEGMENT_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.origin_source_id, str)
                or not self.origin_source_id
                or not isinstance(self.global_span, SourceSpan)
                or self.global_span.end <= self.global_span.start
                or not isinstance(self.ast, StreamingAST)
                or self.global_span.end - self.global_span.start
                != len(self.ast.atoms)
                or not isinstance(self.boundary_source_handle, str)
                or not self.boundary_source_handle
                or not isinstance(self.config, FrameCompilerConfig)
                or self.schema_version != LAWFUL_SEGMENT_SCHEMA):
            _invalid("BAMF_PREFIX_LAWFUL_SEGMENT_INVALID")


def boundary_evidence_digest(segment: LawfulSourceSegment) -> str:
    """Source-adapter evidence identity for a declared lawful split."""
    if not isinstance(segment, LawfulSourceSegment):
        _invalid("BAMF_PREFIX_SPLIT_INPUT_INVALID")
    return contract_digest((
        BOUNDARY_EVIDENCE_SCHEMA, segment.origin_source_id,
        segment.global_span.start, segment.global_span.end,
        segment.ast.source_instance_id, segment.boundary_source_handle))


@dataclass(frozen=True)
class CompiledFrameSegments:
    origin_source_id: str
    global_spans: tuple[SourceSpan, ...]
    boundary_source_handles: tuple[str, ...]
    segments: tuple[CompiledFrameBatch, ...]
    total_source_atoms: int
    total_neural_positions: int
    schema_version: str = COMPILED_SEGMENTS_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.origin_source_id, str)
                or not self.origin_source_id
                or not isinstance(self.global_spans, tuple)
                or not isinstance(self.boundary_source_handles, tuple)
                or not isinstance(self.segments, tuple)
                or not (len(self.global_spans)
                        == len(self.boundary_source_handles)
                        == len(self.segments))
                or any(not isinstance(item, CompiledFrameBatch)
                       for item in self.segments)
                or any(not isinstance(span, SourceSpan)
                       for span in self.global_spans)
                or any(not isinstance(handle, str) or not handle
                       for handle in self.boundary_source_handles)
                or len(set(self.boundary_source_handles))
                != len(self.boundary_source_handles)
                or any(span.end - span.start != segment.visible_end
                       for span, segment in zip(
                           self.global_spans, self.segments))
                or any(span.start != (
                    self.global_spans[index - 1].end if index else 0)
                    for index, span in enumerate(self.global_spans))
                or any(len(item.positions) > MAX_NEURAL_POSITIONS
                       for item in self.segments)
                or type(self.total_source_atoms) is not int
                or self.total_source_atoms != sum(
                    item.visible_end for item in self.segments)
                or type(self.total_neural_positions) is not int
                or self.total_neural_positions != sum(
                    len(item.positions) for item in self.segments)
                or self.schema_version != COMPILED_SEGMENTS_SCHEMA):
            _invalid("BAMF_PREFIX_COMPILED_SEGMENTS_INVALID")


def compile_lawful_segments(
    segments: tuple[LawfulSourceSegment, ...], release: str,
) -> CompiledFrameSegments:
    """Compile only source-declared contiguous boundaries, never truncate."""
    if (not isinstance(segments, tuple) or not segments
            or any(not isinstance(item, LawfulSourceSegment)
                   for item in segments)):
        _invalid("BAMF_PREFIX_SPLIT_INPUT_INVALID")
    origin = segments[0].origin_source_id
    authority = _segment_authority(segments[0].config)
    cursor = 0
    handles = set()
    for segment in segments:
        if (segment.origin_source_id != origin
                or segment.global_span.start != cursor
                or segment.boundary_source_handle in handles
                or _segment_authority(segment.config) != authority):
            _invalid("BAMF_PREFIX_SPLIT_BOUNDARY_INVALID")
        cursor = segment.global_span.end
        handles.add(segment.boundary_source_handle)
        grant = next((
            item for item in segment.config.frontier.grants
            if item.source_handle == segment.boundary_source_handle
        ), None)
        if not _grant_allows(
                grant, boundary_evidence_digest(segment),
                segment.config, release):
            _invalid("BAMF_PREFIX_SPLIT_SOURCE_UNAUTHORIZED")
        if len(segment.ast.atoms) > MAX_NEURAL_POSITIONS:
            _invalid("BAMF_PREFIX_NEURAL_LENGTH_EXCEEDED")
        approved = (
            {item.frame.occurrence_id: item
             for item in segment.config.approved.envelopes}
            if segment.config.approved is not None else {})
        closed = _source_frames(
            segment.ast, len(segment.ast.atoms), approved)
        if len(segment.ast.atoms) + len(closed) > MAX_NEURAL_POSITIONS:
            _invalid("BAMF_PREFIX_NEURAL_LENGTH_EXCEEDED")
    compiled = tuple(
        compile_prefix(
            segment.ast, len(segment.ast.atoms), release, segment.config)
        for segment in segments)
    return CompiledFrameSegments(
        origin, tuple(item.global_span for item in segments),
        tuple(item.boundary_source_handle for item in segments),
        compiled, cursor, sum(len(item.positions) for item in compiled))


def compile_prefix_rows(
    rows: tuple[tuple[StreamingAST, int, FrameCompilerConfig], ...],
    release: str,
) -> CompiledFrameRows:
    """Compile each source row in isolation; padding is never source."""
    if (not isinstance(rows, tuple)
            or any(not isinstance(row, tuple)
                   or len(row) != ROW_COMPILER_INPUT_ARITY
                   for row in rows)):
        _invalid("BAMF_PREFIX_ROWS_INPUT_INVALID")
    compiled = tuple(
        compile_prefix(ast, end, release, config)
        for ast, end, config in rows)
    width = max((len(row.positions) for row in compiled), default=0)
    return CompiledFrameRows(
        compiled,
        tuple(row.positions + (None,) * (width - len(row.positions))
              for row in compiled),
        tuple((True,) * len(row.positions)
              + (False,) * (width - len(row.positions))
              for row in compiled))


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


def validate_partial_visible_forest(
    compiled, source_ast, compiler_config, *, expected_receipt=None,
):
    """A05.4 compatibility entrypoint for source-owned partial-forest validation."""
    from ..partial_visible_forest import validate_partial_visible_forest as validate

    return validate(
        compiled, source_ast, compiler_config,
        expected_receipt=expected_receipt)
