"""Production-owned C09 dependency state for compiled packed frames."""
from __future__ import annotations

from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex, DependencyKind, DependencyRef,
)
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.semantics.frame_compiler import CompiledFrameBatch, CompiledFrameRows
from bilqis_mlx.runtime.atlas_revalidation_common import _invalid, owner_priority
from bilqis_mlx.runtime.atlas_revalidation_evidence import CorrectionEvent, RevalidationFrontier
from bilqis_mlx.runtime.atlas_revalidation_queue import RevalidationProgress, RevalidationQueue
from bilqis_mlx.runtime.atlas_revalidation_runtime import (
    advance_revalidation, apply_correction, next_revalidation_task,
    read_artifact, revalidate_node,
)
from bilqis_mlx.runtime.atlas_source_authority import SourceAuthorityRegistry


def _packed_frame_node(
    row: CompiledFrameBatch, packed, *, include_context: bool = True,
) -> ArtifactNode:
    """Derive C09 identity only from one compiler-owned PackedFrame."""
    from bilqis_mlx.semantics.frame_codec import PackedFrame
    if type(row) is not CompiledFrameBatch or type(packed) is not PackedFrame:
        _invalid("BAMF_C09_PACKED_FRAME_OWNER_INVALID")
    sidecar = packed.sidecar
    source_refs = {
        sidecar.source_instance_id,
        *(ref for item in sidecar.constituents for ref in item.source_references),
    }
    dependencies = {
        DependencyRef(
            DependencyKind.SOURCE,
            ref if ref.startswith("source:") else "source:" + ref)
        for ref in source_refs
    }
    dependencies.update((
        DependencyRef(DependencyKind.RELEASE, "release:" + packed.semantic_release),
        DependencyRef(
            DependencyKind.OPERATOR,
            "operator:frame-compiler:" + row.schema_version),
        DependencyRef(
            DependencyKind.POLICY,
            "policy:" + contract_digest((row.scope, row.policy_version[0], row.policy_version[1]))),
        DependencyRef(
            DependencyKind.RIGHTS,
            "rights:" + contract_digest((row.policy_version[2], row.policy_version[3]))),
    ))
    if include_context and row.context_digest is not None:
        dependencies.add(DependencyRef(
            DependencyKind.TIME,
            "time:asof:context:" + row.context_digest,
        ))
    impact, exigency = owner_priority(ArtifactKind.PACKED_FRAME)
    return ArtifactNode(
        artifact_id="frame:" + sidecar.occurrence_id,
        kind=ArtifactKind.PACKED_FRAME,
        content_digest=packed.projection_sha256,
        eligible=True,
        immediate_dependencies=tuple(sorted(dependencies)),
        impact=impact,
        exigency=exigency,
    )


def _context_view_node(
    physical: ArtifactNode, context_digest: str,
) -> ArtifactNode:
    impact, exigency = owner_priority(ArtifactKind.PACKED_FRAME)
    return ArtifactNode(
        artifact_id=physical.artifact_id + ":context:" + context_digest,
        kind=ArtifactKind.PACKED_FRAME,
        content_digest=physical.content_digest,
        eligible=True,
        immediate_dependencies=tuple(sorted((
            physical.reference,
            DependencyRef(
                DependencyKind.TIME,
                "time:asof:context:" + context_digest),
        ))),
        impact=impact,
        exigency=exigency,
    )


class PackedFrameArtifactOwner:
    """Own correction state for actual A05 PackedFrame objects consumed by B03."""

    def __init__(self, rows: CompiledFrameRows):
        if type(rows) is not CompiledFrameRows or not rows.rows:
            _invalid("BAMF_C09_PACKED_FRAME_OWNER_INVALID")
        self._rows = rows
        occurrences: dict[str, list[tuple[CompiledFrameBatch, object]]] = {}
        for row in rows.rows:
            for position in row.positions:
                if position.packed is None:
                    continue
                artifact_id = "frame:" + position.packed.sidecar.occurrence_id
                occurrences.setdefault(artifact_id, []).append((row, position.packed))
        physical_nodes = {}
        view_nodes = {}
        origin_context_keys = []
        multi_context_artifact_ids = set()
        for artifact_id, items in occurrences.items():
            contexts = {row.context_digest for row, _packed in items}
            multi_context = len(contexts) > 1
            if multi_context:
                multi_context_artifact_ids.add(artifact_id)
            node = _packed_frame_node(
                items[0][0], items[0][1], include_context=not multi_context)
            physical_nodes[artifact_id] = node
            for row, packed in items:
                candidate = _packed_frame_node(
                    row, packed, include_context=not multi_context)
                if candidate != node:
                    _invalid("BAMF_C09_PACKED_FRAME_IDENTITY_DRIFT")
                if multi_context:
                    if row.context_digest is None:
                        _invalid("BAMF_C09_PACKED_FRAME_IDENTITY_DRIFT")
                    view = _context_view_node(node, row.context_digest)
                    prior = view_nodes.get(view.artifact_id)
                    if prior is not None and prior != view:
                        _invalid("BAMF_C09_PACKED_FRAME_IDENTITY_DRIFT")
                    view_nodes[view.artifact_id] = view
                    origin_context_keys.append(view.artifact_id)
        self._physical_artifact_ids = tuple(sorted(physical_nodes))
        self._multi_context_artifact_ids = frozenset(multi_context_artifact_ids)
        self._origin_context_keys = tuple(sorted(set(origin_context_keys)))
        nodes = {**physical_nodes, **view_nodes}
        self._index = DependencyIndex.build(tuple(nodes.values()))
        self._queue: RevalidationQueue | None = None
        self._context_dependency_overrides: dict[
            str, tuple[DependencyRef, ...],
        ] = {}

    @property
    def index(self) -> DependencyIndex:
        return self._index

    @property
    def physical_nodes(self) -> tuple[ArtifactNode, ...]:
        return tuple(self._index.node(item) for item in self._physical_artifact_ids)

    @property
    def origin_context_keys(self) -> tuple[str, ...]:
        return self._origin_context_keys

    @property
    def cache_identity(self) -> tuple[str, ...]:
        if not self._multi_context_artifact_ids:
            return self._physical_artifact_ids
        return ("multi-context", *self._physical_artifact_ids, *self._origin_context_keys)

    @property
    def current_context_dependencies(self) -> tuple[DependencyRef, ...]:
        if not self._multi_context_artifact_ids:
            return ()
        return tuple(sorted({
            ref
            for key in self._origin_context_keys
            for ref in self._index.node(key).immediate_dependencies
            if ref.kind is DependencyKind.TIME
        }))

    def _install_context_revalidation(
        self, index: DependencyIndex, transition,
    ) -> None:
        if (not isinstance(index, DependencyIndex)
                or {node.artifact_id for node in index.nodes}
                != {node.artifact_id for node in self._index.nodes}):
            _invalid("BAMF_C09_CONTEXT_REVALIDATION_INDEX_DRIFT")
        previous = self._index.node(transition.artifact_id)
        updated = index.node(transition.artifact_id)
        if (previous.content_digest != transition.previous_content_digest
                or updated.content_digest != transition.new_content_digest
                or updated.immediate_dependencies
                != transition.new_dependencies):
            _invalid("BAMF_C09_CONTEXT_REVALIDATION_INDEX_DRIFT")
        self._index = index
        if previous.content_digest == updated.content_digest:
            self._context_dependency_overrides[
                updated.artifact_id] = updated.immediate_dependencies
        else:
            self._context_dependency_overrides.pop(updated.artifact_id, None)
        return True

    @property
    def queue(self) -> RevalidationQueue | None:
        return self._queue

    def node_for(self, packed) -> ArtifactNode:
        from bilqis_mlx.semantics.frame_codec import PackedFrame
        if type(packed) is not PackedFrame:
            _invalid("BAMF_C09_PACKED_FRAME_OWNER_INVALID")
        return self._index.node("frame:" + packed.sidecar.occurrence_id)

    def require_row(self, row: CompiledFrameBatch) -> tuple[ArtifactNode, ...]:
        if type(row) is not CompiledFrameBatch or row not in self._rows.rows:
            _invalid("BAMF_C09_PACKED_FRAME_OWNER_MISMATCH")
        result = []
        for position in row.positions:
            if position.packed is None:
                continue
            node = self.node_for(position.packed)
            multi_context = node.artifact_id in self._multi_context_artifact_ids
            expected = _packed_frame_node(
                row, position.packed, include_context=not multi_context)
            dependency_match = (
                node.immediate_dependencies == expected.immediate_dependencies
                or self._context_dependency_overrides.get(node.artifact_id)
                == node.immediate_dependencies)
            if (node.content_digest != expected.content_digest
                    or not dependency_match):
                _invalid("BAMF_C09_PACKED_FRAME_CONTENT_DRIFT")
            from bilqis_mlx.runtime.accepted_correction_runtime import require_pending_corrections
            require_pending_corrections(self, node.artifact_id)
            if self._queue is not None:
                node = read_artifact(self._index, self._queue, node.artifact_id)
            elif not node.eligible:
                _invalid("BAMF_C09_ARTIFACT_INELIGIBLE")
            if multi_context:
                if row.context_digest is None:
                    _invalid("BAMF_C09_PACKED_FRAME_OWNER_MISMATCH")
                view_id = (
                    "frame:" + position.packed.sidecar.occurrence_id
                    + ":context:" + row.context_digest)
                view = self._index.node(view_id)
                require_pending_corrections(self, view.artifact_id)
                if self._queue is not None:
                    view = read_artifact(self._index, self._queue, view.artifact_id)
                elif not view.eligible:
                    _invalid("BAMF_C09_ARTIFACT_INELIGIBLE")
                time_refs = tuple(
                    ref for ref in view.immediate_dependencies
                    if ref.kind is DependencyKind.TIME)
                node = ArtifactNode(
                    node.artifact_id, node.kind, node.content_digest,
                    node.eligible and view.eligible,
                    tuple(sorted((*node.immediate_dependencies, *time_refs))),
                    impact=node.impact, exigency=node.exigency)
            result.append(node)
        return tuple(result)

    def apply_correction(
        self, event: CorrectionEvent, authority_registry: SourceAuthorityRegistry,
    ) -> RevalidationQueue:
        from bilqis_mlx.runtime.accepted_correction_runtime import (
            require_bound_owner_registry,
        )
        authority_registry = require_bound_owner_registry(self, authority_registry)
        self._queue = apply_correction(event, self._index, authority_registry)
        return self._queue

    def advance(
        self, frontier: RevalidationFrontier,
        authority_registry: SourceAuthorityRegistry,
    ) -> RevalidationProgress:
        from bilqis_mlx.runtime.accepted_correction_runtime import (
            require_bound_owner_registry,
        )
        authority_registry = require_bound_owner_registry(self, authority_registry)
        if self._queue is None:
            _invalid("BAMF_C09_PACKED_FRAME_REVALIDATION_NOT_HELD")
        task = next_revalidation_task(self._index, self._queue)
        if task is None:
            _invalid("BAMF_C09_PACKED_FRAME_REVALIDATION_NOT_PENDING")
        transition = revalidate_node(
            self._index.node(task.artifact_id), frontier, authority_registry)
        progress = advance_revalidation(
            self._index, self._queue, transition, authority_registry)
        self._index = progress.index
        self._queue = progress.queue
        return progress
