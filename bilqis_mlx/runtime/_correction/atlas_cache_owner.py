"""C09 correction ownership for actual B14 exact-cache artifacts."""
from __future__ import annotations

import hashlib

from bilqis_mlx.runtime.atlas_cache_binding import (
    CacheArtifact, CacheBinding, binding_digest, require_cache_binding,
)
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex, DependencyKind, DependencyRef,
)
from bilqis_mlx.runtime._revalidation_authority import SourceAuthorityRegistry
from bilqis_mlx.runtime._revalidation_base import _invalid
from bilqis_mlx.runtime._revalidation_engine import (
    advance_revalidation, apply_correction, next_revalidation_task,
    read_artifact, revalidate_node,
)
from bilqis_mlx.runtime._revalidation_events import CorrectionEvent, RevalidationFrontier
from bilqis_mlx.runtime._revalidation_queue import RevalidationProgress, RevalidationQueue


def cache_artifact_digest(artifact: CacheArtifact) -> str:
    """Hash the exact stored cache representation, not caller metadata."""
    if not isinstance(artifact, CacheArtifact):
        _invalid("BAMF_C09_EXACT_CACHE_OWNER_INVALID")
    digest = hashlib.sha256()
    for value in (
        artifact.mode.encode("ascii"),
        artifact.true_vectors.to_bytes(8, "big"),
        artifact.padded_vectors.to_bytes(8, "big"),
        artifact.head_width.to_bytes(8, "big"),
        artifact.binding_sha256,
        artifact.header_bytes or b"",
        artifact.direction_codes,
        artifact.relative_norms,
        artifact.block_max_norms_fp32,
        artifact.fp32_payload,
    ):
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
    return digest.hexdigest()


def _dependencies(binding: CacheBinding) -> tuple[DependencyRef, ...]:
    return tuple(sorted((
        DependencyRef(DependencyKind.RELEASE, "generation:" + binding.generation_sha256),
        DependencyRef(DependencyKind.SOURCE, "lineage:" + binding.lineage_sha256),
        DependencyRef(DependencyKind.OPERATOR, "topology:" + binding.topology_sha256),
        DependencyRef(DependencyKind.RIGHTS, "rights:" + binding.source_rights_sha256),
        DependencyRef(DependencyKind.SOURCE, "prefix:" + binding.causal_prefix_sha256),
        DependencyRef(DependencyKind.POLICY, "masks:" + binding.masks_sha256),
        DependencyRef(DependencyKind.POLICY, "scope:" + binding.scope_sha256),
        DependencyRef(DependencyKind.SOURCE, "key:" + binding.key_sha256),
        DependencyRef(DependencyKind.TIME, "offset:" + str(binding.offset)),
    )))


def _node(artifact: CacheArtifact, binding: CacheBinding) -> ArtifactNode:
    require_cache_binding(artifact, binding)
    return ArtifactNode(
        artifact_id="cache:" + binding_digest(binding).hex(),
        kind=ArtifactKind.EXACT_CACHE,
        content_digest=cache_artifact_digest(artifact),
        eligible=True,
        immediate_dependencies=_dependencies(binding),
        impact=0,
        exigency=0,
    )


class ExactCacheArtifactOwner:
    """Retain correction holds across actual cache reads and recomputation."""

    def __init__(self, artifact: CacheArtifact, binding: CacheBinding):
        node = _node(artifact, binding)
        self._artifact_id = node.artifact_id
        self._index = DependencyIndex.build((node,))
        self._queue: RevalidationQueue | None = None

    @property
    def current_node(self) -> ArtifactNode:
        return self._index.node(self._artifact_id)

    @property
    def queue(self) -> RevalidationQueue | None:
        return self._queue

    @property
    def rights_dependency(self) -> DependencyRef:
        return next(ref for ref in self.current_node.immediate_dependencies
                    if ref.kind is DependencyKind.RIGHTS)

    def require(self, artifact: CacheArtifact, binding: CacheBinding) -> ArtifactNode:
        expected = _node(artifact, binding)
        if expected.artifact_id != self._artifact_id:
            _invalid("BAMF_C09_EXACT_CACHE_OWNER_MISMATCH")
        node = self.current_node
        if (node.content_digest != expected.content_digest
                or node.immediate_dependencies != expected.immediate_dependencies):
            _invalid("BAMF_C09_EXACT_CACHE_CONTENT_DRIFT")
        if self._queue is not None:
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
            _invalid("BAMF_C09_EXACT_CACHE_REVALIDATION_NOT_HELD")
        task = next_revalidation_task(self._index, self._queue)
        if task is None:
            _invalid("BAMF_C09_EXACT_CACHE_REVALIDATION_NOT_PENDING")
        transition = revalidate_node(
            self._index.node(task.artifact_id), frontier, authority_registry)
        progress = advance_revalidation(
            self._index, self._queue, transition, authority_registry)
        self._index = progress.index
        self._queue = progress.queue
        return progress
