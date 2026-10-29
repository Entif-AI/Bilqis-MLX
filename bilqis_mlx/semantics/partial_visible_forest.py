"""A05.4 source-owned validation for causally partial visible frame forests."""
from __future__ import annotations

from dataclasses import dataclass
import re

from .context_eligibility import ContextEligibility
from .domains import contract_digest
from .frame_compiler import (
    CompiledFrameBatch,
    FrameCompilerConfig,
    StreamingAST,
    _closure_end,
    _invalid,
    compile_prefix,
    reconstruct,
)
from .frame_schema import (
    AtomicFrame,
    FrameInstance,
    FrameSchema,
    FrameTree,
    validate_frame_tree,
)


PARTIAL_PARENT_SCHEMA = "bilqis.partial-visible-parent/v1"
PARTIAL_FOREST_SCHEMA = "bilqis.partial-visible-forest-receipt/v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class HiddenParentProvenance:
    """Non-visible parent authority without future member content."""

    child_occurrence_id: str
    parent_occurrence_id: str
    parent_frame_handle: str
    provenance_digest: str
    schema_version: str = PARTIAL_PARENT_SCHEMA

    def __post_init__(self) -> None:
        if (not all(isinstance(item, str) and _SHA.fullmatch(item)
                    for item in (
                        self.child_occurrence_id,
                        self.parent_occurrence_id,
                        self.provenance_digest))
                or not isinstance(self.parent_frame_handle, str)
                or not self.parent_frame_handle
                or self.schema_version != PARTIAL_PARENT_SCHEMA):
            _invalid("BAMF_PREFIX_PARTIAL_PARENT_INVALID")


def _visible_tree_identity(tree: FrameTree) -> tuple:
    return (
        tree.root.occurrence_id,
        tree.root.content_digest,
        tuple(_visible_tree_identity(child) for child in tree.children),
    )


def _partial_forest_digest(
    source_instance_id: str,
    semantic_release: str,
    visible_end: int,
    compiler_cache_key: str,
    visible_forest: tuple[FrameTree, ...],
    visible_frame_handles: tuple[tuple[str, str], ...],
    hidden_parents: tuple[HiddenParentProvenance, ...],
) -> str:
    return contract_digest((
        PARTIAL_FOREST_SCHEMA,
        source_instance_id,
        semantic_release,
        visible_end,
        compiler_cache_key,
        tuple(_visible_tree_identity(tree) for tree in visible_forest),
        visible_frame_handles,
        tuple((
            item.child_occurrence_id,
            item.parent_occurrence_id,
            item.parent_frame_handle,
            item.provenance_digest,
        ) for item in hidden_parents),
    ))


@dataclass(frozen=True)
class PartialVisibleForestReceipt:
    """Visible frame forest plus opaque provenance for non-visible parents."""

    source_instance_id: str
    semantic_release: str
    visible_end: int
    compiler_cache_key: str
    visible_forest: tuple[FrameTree, ...]
    visible_frame_handles: tuple[tuple[str, str], ...]
    hidden_parents: tuple[HiddenParentProvenance, ...]
    digest: str
    schema_version: str = PARTIAL_FOREST_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.source_instance_id, str)
                or not self.source_instance_id
                or not isinstance(self.semantic_release, str)
                or not _SHA.fullmatch(self.semantic_release)
                or type(self.visible_end) is not int or self.visible_end < 0
                or not isinstance(self.compiler_cache_key, str)
                or not _SHA.fullmatch(self.compiler_cache_key)
                or not isinstance(self.visible_forest, tuple)
                or any(not isinstance(tree, FrameTree)
                       for tree in self.visible_forest)
                or not isinstance(self.visible_frame_handles, tuple)
                or any(not isinstance(item, tuple) or len(item) != 2
                       or not isinstance(item[0], str) or not _SHA.fullmatch(item[0])
                       or not isinstance(item[1], str) or not item[1]
                       for item in self.visible_frame_handles)
                or not isinstance(self.hidden_parents, tuple)
                or any(not isinstance(item, HiddenParentProvenance)
                       for item in self.hidden_parents)
                or not isinstance(self.digest, str) or not _SHA.fullmatch(self.digest)
                or self.digest != _partial_forest_digest(
                    self.source_instance_id,
                    self.semantic_release,
                    self.visible_end,
                    self.compiler_cache_key,
                    self.visible_forest,
                    self.visible_frame_handles,
                    self.hidden_parents)
                or self.schema_version != PARTIAL_FOREST_SCHEMA):
            _invalid("BAMF_PREFIX_PARTIAL_RECEIPT_INVALID")


def _source_tree_index(
    ast: StreamingAST,
) -> tuple[
    dict[str, FrameInstance | AtomicFrame],
    dict[str, str | None],
]:
    frames: dict[str, FrameInstance | AtomicFrame] = {}
    parents: dict[str, str | None] = {}

    def walk(tree: FrameTree, parent_occurrence_id: str | None) -> None:
        validate_frame_tree(tree)
        frame = tree.root
        if frame.occurrence_id in frames:
            _invalid("BAMF_PREFIX_PARTIAL_SOURCE_DUPLICATE")
        frames[frame.occurrence_id] = frame
        parents[frame.occurrence_id] = parent_occurrence_id
        for child in tree.children:
            walk(child, frame.occurrence_id)

    for tree in ast.frames:
        walk(tree, None)
    return frames, parents


def _visible_forest_frames(
    forest: tuple[FrameTree, ...],
) -> tuple[FrameInstance | AtomicFrame, ...]:
    frames = []

    def walk(tree: FrameTree) -> None:
        frames.append(tree.root)
        for child in tree.children:
            walk(child)

    for tree in forest:
        walk(tree)
    return tuple(frames)


def _hidden_parent_provenance(
    child: FrameInstance | AtomicFrame,
    parent: FrameInstance | AtomicFrame,
    envelope: ContextEligibility,
    schemas: dict[tuple[str, int], FrameSchema],
) -> HiddenParentProvenance:
    if isinstance(parent, FrameInstance):
        schema = schemas.get(
            (parent.frame_schema_id, parent.frame_schema_revision))
        if schema is None:
            _invalid("BAMF_PREFIX_PARTIAL_AUTHORITY_DRIFT")
        frame_authority = (
            parent.frame_schema_id,
            parent.frame_schema_revision,
            schema.scope,
        )
    else:
        frame_authority = ("<atomic>", 0, parent.ast_construct)
    provenance_digest = contract_digest((
        PARTIAL_PARENT_SCHEMA,
        parent.occurrence_id,
        parent.source_instance_id,
        parent.structural_path,
        (parent.source_span.start, parent.source_span.end),
        parent.parent_occurrence_id,
        parent.causal_prefix_end,
        frame_authority,
        envelope.frame_handle,
        envelope.source_handle,
        envelope.semantic_release,
        envelope.scope,
        envelope.source_regime,
        envelope.policy_epoch,
        envelope.rights_epoch,
        envelope.correction_generation,
    ))
    return HiddenParentProvenance(
        child.occurrence_id,
        parent.occurrence_id,
        envelope.frame_handle,
        provenance_digest,
    )


def validate_partial_visible_forest(
    compiled: CompiledFrameBatch,
    source_ast: StreamingAST,
    compiler_config: FrameCompilerConfig,
    *,
    expected_receipt: PartialVisibleForestReceipt | None = None,
) -> PartialVisibleForestReceipt:
    """Validate a visible prefix without synthesizing or rewriting hidden parents.

    Hidden-parent provenance binds source/context metadata only. Future bindings and
    member content never enter this receipt or the accepted compiler prefix identity.
    """
    if (not isinstance(compiled, CompiledFrameBatch)
            or not isinstance(source_ast, StreamingAST)
            or not isinstance(compiler_config, FrameCompilerConfig)
            or (expected_receipt is not None
                and not isinstance(expected_receipt, PartialVisibleForestReceipt))):
        _invalid("BAMF_PREFIX_PARTIAL_INPUT_INVALID")
    compiled.__post_init__()
    if (source_ast.source_instance_id != compiled.source_instance_id
            or compiler_config.task.semantic_release != compiled.semantic_release
            or compiler_config.schema_map.semantic_release != compiled.semantic_release
            or compiler_config.schema_map != compiled.schema_map
            or compiler_config.task.scope != compiled.scope
            or compiled.policy_version != (
                compiler_config.policy.policy_id,
                compiler_config.policy.policy_epoch,
                compiler_config.policy.rights_epoch,
                compiler_config.frontier.correction_generation)):
        _invalid("BAMF_PREFIX_PARTIAL_AUTHORITY_DRIFT")

    visible = reconstruct(compiled)
    visible_frames = _visible_forest_frames(visible.frames)
    visible_by_occurrence = {
        frame.occurrence_id: frame for frame in visible_frames}
    if len(visible_by_occurrence) != len(visible_frames):
        _invalid("BAMF_PREFIX_PARTIAL_VISIBLE_DUPLICATE")

    source_frames, source_parents = _source_tree_index(source_ast)
    for occurrence_id, source_frame in source_frames.items():
        if source_frame.parent_occurrence_id != source_parents[occurrence_id]:
            _invalid("BAMF_PREFIX_PARTIAL_PARENT_ORPHAN")

    envelopes = {}
    if compiler_config.approved is not None:
        for envelope in compiler_config.approved.envelopes:
            occurrence_id = envelope.frame.occurrence_id
            if occurrence_id in envelopes:
                _invalid("BAMF_PREFIX_PARTIAL_AUTHORITY_DRIFT")
            envelopes[occurrence_id] = envelope
    schemas = {
        (schema.schema_id, schema.revision): schema
        for schema in compiler_config.schemas
    }

    visible_handles = []
    hidden_parents = []
    visible_occurrences = set(visible_by_occurrence)
    for frame in visible_frames:
        source_frame = source_frames.get(frame.occurrence_id)
        if source_frame is None:
            _invalid("BAMF_PREFIX_PARTIAL_SOURCE_DRIFT")
        actual_parent = source_parents[frame.occurrence_id]
        if frame.parent_occurrence_id != actual_parent:
            _invalid("BAMF_PREFIX_PARTIAL_PARENT_ORPHAN")
        if source_frame != frame:
            _invalid("BAMF_PREFIX_PARTIAL_SOURCE_DRIFT")
        envelope = envelopes.get(frame.occurrence_id)
        if (envelope is None
                or envelope.frame != source_frame
                or envelope.semantic_release != compiled.semantic_release
                or envelope.scope != compiled.scope
                or envelope.frame.source_instance_id != compiled.source_instance_id
                or _closure_end(frame, envelopes) > compiled.visible_end):
            _invalid("BAMF_PREFIX_PARTIAL_AUTHORITY_DRIFT")
        visible_handles.append((frame.occurrence_id, envelope.frame_handle))

        parent_occurrence = frame.parent_occurrence_id
        if (parent_occurrence is None
                or parent_occurrence in visible_occurrences):
            continue
        parent = source_frames.get(parent_occurrence)
        if parent is None:
            _invalid("BAMF_PREFIX_PARTIAL_PARENT_ORPHAN")
        parent_envelope = envelopes.get(parent_occurrence)
        if (parent_envelope is None
                or parent_envelope.frame != parent
                or parent.source_instance_id != compiled.source_instance_id
                or parent_envelope.semantic_release != compiled.semantic_release
                or parent_envelope.scope != compiled.scope):
            _invalid("BAMF_PREFIX_PARTIAL_AUTHORITY_DRIFT")
        if _closure_end(parent, envelopes) <= compiled.visible_end:
            _invalid("BAMF_PREFIX_PARTIAL_VISIBILITY_DRIFT")
        hidden_parents.append(_hidden_parent_provenance(
            frame, parent, parent_envelope, schemas))

    recompiled = compile_prefix(
        source_ast, compiled.visible_end,
        compiled.semantic_release, compiler_config)
    if recompiled != compiled:
        _invalid("BAMF_PREFIX_PARTIAL_COMPILATION_DRIFT")

    visible_handles = tuple(sorted(visible_handles))
    hidden_parents = tuple(sorted(
        hidden_parents,
        key=lambda item: (
            item.child_occurrence_id, item.parent_occurrence_id)))
    digest = _partial_forest_digest(
        compiled.source_instance_id,
        compiled.semantic_release,
        compiled.visible_end,
        compiled.cache_key,
        visible.frames,
        visible_handles,
        hidden_parents,
    )
    receipt = PartialVisibleForestReceipt(
        compiled.source_instance_id,
        compiled.semantic_release,
        compiled.visible_end,
        compiled.cache_key,
        visible.frames,
        visible_handles,
        hidden_parents,
        digest,
    )
    if expected_receipt is not None and receipt != expected_receipt:
        _invalid("BAMF_PREFIX_PARTIAL_RECEIPT_DRIFT")
    return receipt
