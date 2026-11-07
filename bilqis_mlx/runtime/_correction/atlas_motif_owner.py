"""C09 correction ownership for B13-authenticated retained motif manifests."""
from __future__ import annotations

from bilqis_mlx.learning.atlas_engram import MotifManifest
from bilqis_mlx.learning.frame_encoder import CompiledEncoderInput
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex, DependencyKind, DependencyRef,
)
from bilqis_mlx.runtime.atlas_revalidation_common import _invalid
from bilqis_mlx.runtime.atlas_revalidation_evidence import (
    CorrectionEvent, RevalidationFrontier,
)
from bilqis_mlx.runtime.atlas_revalidation_queue import (
    RevalidationProgress, RevalidationQueue,
)
from bilqis_mlx.runtime.atlas_revalidation_runtime import (
    advance_revalidation, apply_correction, next_revalidation_task,
    read_artifact, revalidate_node,
)
from bilqis_mlx.runtime.atlas_source_authority import SourceAuthorityRegistry


def _motif_node(cache, compiled: CompiledEncoderInput) -> tuple[ArtifactNode, tuple[str, ...]]:
    """Derive one retained-manifest node from authenticated B13 + A05 custody."""
    from bilqis_mlx.runtime.bamf_bundle.execution_cache import AcceptedExecutionCache

    if type(cache) is not AcceptedExecutionCache or type(compiled) is not CompiledEncoderInput:
        _invalid("BAMF_C09_MOTIF_OWNER_INVALID")
    manifest = cache.motif_manifest
    if type(manifest) is not MotifManifest or manifest.digest != compiled.extents.motif_key_map_digest:
        _invalid("BAMF_C09_MOTIF_MANIFEST_DRIFT")
    frame_nodes = compiled.packed_frame_artifact_owner.index.nodes
    frame_ids = tuple(node.artifact_id for node in frame_nodes)
    dependencies = {
        *(node.reference for node in frame_nodes),
        DependencyRef(DependencyKind.RELEASE, "semantic-release:" + manifest.semantic_release),
        DependencyRef(DependencyKind.RELEASE, "generation:" + cache.generation_binding),
        DependencyRef(DependencyKind.SOURCE, "accepted-manifest:" + cache.accepted_manifest_sha256),
        DependencyRef(DependencyKind.SOURCE, "run:" + cache.run_id),
        DependencyRef(DependencyKind.TIME, "generation:" + str(cache.generation)),
    }
    return ArtifactNode(
        artifact_id="motif:" + manifest.digest,
        kind=ArtifactKind.MOTIF,
        content_digest=manifest.digest,
        eligible=True,
        immediate_dependencies=tuple(sorted(dependencies)),
        impact=0,
        exigency=0,
    ), frame_ids


class MotifArtifactOwner:
    """Hold retained motif state before it can alter the next B11 hidden state."""

    def __init__(self, cache, compiled: CompiledEncoderInput):
        motif, frame_ids = _motif_node(cache, compiled)
        frame_nodes = compiled.packed_frame_artifact_owner.index.nodes
        self._artifact_id = motif.artifact_id
        self._frame_ids = frame_ids
        self._index = DependencyIndex.build((*frame_nodes, motif))
        self._queue: RevalidationQueue | None = None

    @property
    def current_node(self) -> ArtifactNode:
        return self._index.node(self._artifact_id)

    @property
    def index(self) -> DependencyIndex:
        return self._index

    @property
    def queue(self) -> RevalidationQueue | None:
        return self._queue

    @property
    def source_dependencies(self) -> tuple[DependencyRef, ...]:
        return tuple(sorted({
            ref
            for artifact_id in self._frame_ids
            for ref in self._index.node(artifact_id).immediate_dependencies
            if ref.kind is DependencyKind.SOURCE
        }))

    def require(self, cache, compiled: CompiledEncoderInput) -> ArtifactNode:
        expected, frame_ids = _motif_node(cache, compiled)
        if frame_ids != self._frame_ids or expected.artifact_id != self._artifact_id:
            _invalid("BAMF_C09_MOTIF_OWNER_MISMATCH")
        node = self.current_node
        if (node.content_digest != expected.content_digest
                or node.immediate_dependencies != expected.immediate_dependencies):
            _invalid("BAMF_C09_MOTIF_CONTENT_DRIFT")
        # A direct source correction holds its actual A05 input before the
        # manifest lookup can influence hidden state. Downstream motif holding
        # is propagated only when the recomputed input changes.
        if self._queue is not None:
            for artifact_id in self._frame_ids:
                read_artifact(self._index, self._queue, artifact_id)
            return read_artifact(self._index, self._queue, node.artifact_id)
        if not node.eligible:
            _invalid("BAMF_C09_ARTIFACT_INELIGIBLE")
        return node

    def apply_correction(
        self, event: CorrectionEvent, authority_registry: SourceAuthorityRegistry,
    ) -> RevalidationQueue:
        self._queue = apply_correction(event, self._index, authority_registry)
        return self._queue

    def advance(
        self, frontier: RevalidationFrontier,
        authority_registry: SourceAuthorityRegistry,
    ) -> RevalidationProgress:
        if self._queue is None:
            _invalid("BAMF_C09_MOTIF_REVALIDATION_NOT_HELD")
        task = next_revalidation_task(self._index, self._queue)
        if task is None:
            _invalid("BAMF_C09_MOTIF_REVALIDATION_NOT_PENDING")
        transition = revalidate_node(
            self._index.node(task.artifact_id), frontier, authority_registry)
        progress = advance_revalidation(
            self._index, self._queue, transition, authority_registry)
        self._index = progress.index
        self._queue = progress.queue
        return progress


__all__ = ("MotifArtifactOwner",)
