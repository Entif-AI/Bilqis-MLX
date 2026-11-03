"""Production-owned C09 dependency state for released Atlas features."""
from __future__ import annotations

from bilqis_mlx.semantics.atlas_features import AtlasFeatures, FeatureSchema
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex, DependencyKind, DependencyRef,
)
from bilqis_mlx.runtime._revalidation_base import _invalid
from bilqis_mlx.runtime._revalidation_authority import SourceAuthorityRegistry
from bilqis_mlx.runtime._revalidation_engine import (
    advance_revalidation, apply_correction, next_revalidation_task,
    read_artifact, revalidate_node,
)
from bilqis_mlx.runtime._revalidation_events import CorrectionEvent, RevalidationFrontier
from bilqis_mlx.runtime._revalidation_queue import RevalidationProgress, RevalidationQueue


def _artifact_id(features: AtlasFeatures) -> str:
    return "atlas-feature:" + features.digest


def _source_ref(features: AtlasFeatures) -> DependencyRef:
    return DependencyRef(DependencyKind.SOURCE, "source:" + features.source_bundle_id)


def _release_ref(features: AtlasFeatures) -> DependencyRef:
    return DependencyRef(DependencyKind.RELEASE, "release:" + features.semantic_release)


def _atlas_ref(features: AtlasFeatures) -> DependencyRef:
    return DependencyRef(DependencyKind.SOURCE, "atlas:" + features.atlas_bundle_id)


def _node(features: AtlasFeatures, predecessor: AtlasFeatures | None) -> ArtifactNode:
    dependencies = [_source_ref(features), _release_ref(features), _atlas_ref(features)]
    if predecessor is not None:
        dependencies.append(DependencyRef(DependencyKind.ARTIFACT, _artifact_id(predecessor)))
    return ArtifactNode(
        artifact_id=_artifact_id(features),
        kind=ArtifactKind.ATLAS_FEATURE,
        content_digest=features.digest,
        eligible=True,
        immediate_dependencies=tuple(sorted(dependencies)),
        impact=0,
        exigency=0,
    )


class AtlasFeatureArtifactOwner:
    """Retain C09 holds across reads without accepting caller-authored nodes."""

    def __init__(self, features: AtlasFeatures, feature_schema: FeatureSchema):
        if type(features) is not AtlasFeatures or type(feature_schema) is not FeatureSchema:
            _invalid("BAMF_C09_ATLAS_FEATURE_OWNER_INVALID")
        predecessor = feature_schema.predecessor
        if ((predecessor is None) != (features.predecessor_digest is None)
                or (predecessor is not None
                    and predecessor.digest != features.predecessor_digest)
                or (predecessor is not None
                    and predecessor.predecessor_digest is not None)):
            _invalid("BAMF_C09_ATLAS_FEATURE_PREDECESSOR_INCOMPLETE")
        nodes = (() if predecessor is None else (_node(predecessor, None),))
        self._index = DependencyIndex.build((*nodes, _node(features, predecessor)))
        self._current_artifact_id = _artifact_id(features)
        self._queue: RevalidationQueue | None = None

    @property
    def source_dependency(self) -> DependencyRef:
        return next(ref for ref in self.current_node.immediate_dependencies
                    if ref.kind is DependencyKind.SOURCE and ref.key.startswith("source:"))

    @property
    def current_node(self) -> ArtifactNode:
        return self._index.node(self._current_artifact_id)

    @property
    def queue(self) -> RevalidationQueue | None:
        return self._queue

    def require(self, features: AtlasFeatures) -> ArtifactNode:
        if type(features) is not AtlasFeatures or _artifact_id(features) != self._current_artifact_id:
            _invalid("BAMF_C09_ATLAS_FEATURE_OWNER_MISMATCH")
        node = self.current_node
        if node.content_digest != features.digest:
            _invalid("BAMF_C09_ATLAS_FEATURE_CONTENT_DRIFT")
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
            _invalid("BAMF_C09_ATLAS_FEATURE_REVALIDATION_NOT_HELD")
        task = next_revalidation_task(self._index, self._queue)
        if task is None:
            _invalid("BAMF_C09_ATLAS_FEATURE_REVALIDATION_NOT_PENDING")
        transition = revalidate_node(
            self._index.node(task.artifact_id), frontier, authority_registry)
        progress = advance_revalidation(
            self._index, self._queue, transition, authority_registry)
        self._index = progress.index
        self._queue = progress.queue
        return progress
