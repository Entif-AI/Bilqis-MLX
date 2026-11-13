"""Production-owned C09 dependency state for released Atlas features."""
from __future__ import annotations

from bilqis_mlx.semantics.atlas_features import (
    FEATURE_MANIFEST_OPERATOR_ID,
    AtlasFeatures,
    FeatureSchema,
)
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex, DependencyKind, DependencyRef,
)
from bilqis_mlx.runtime.atlas_revalidation_common import _invalid, owner_priority
from bilqis_mlx.runtime.atlas_source_authority import SourceAuthorityRegistry
from bilqis_mlx.runtime.atlas_revalidation_runtime import (
    advance_revalidation, apply_correction, next_revalidation_task,
    read_artifact, revalidate_node,
)
from bilqis_mlx.runtime.atlas_revalidation_evidence import CorrectionEvent, RevalidationFrontier
from bilqis_mlx.runtime.atlas_revalidation_queue import RevalidationProgress, RevalidationQueue
from bilqis_mlx.runtime.atlas_packed_frame_owner import PackedFrameArtifactOwner


def _artifact_id(features: AtlasFeatures) -> str:
    return "atlas-feature:" + features.digest


def _source_ref(features: AtlasFeatures) -> DependencyRef:
    return DependencyRef(DependencyKind.SOURCE, "source:" + features.source_bundle_id)


def _release_ref(features: AtlasFeatures) -> DependencyRef:
    return DependencyRef(DependencyKind.RELEASE, "release:" + features.semantic_release)


def _atlas_ref(features: AtlasFeatures) -> DependencyRef:
    return DependencyRef(DependencyKind.SOURCE, "atlas:" + features.atlas_bundle_id)


def _feature_schema_refs(feature_schema: FeatureSchema) -> tuple[DependencyRef, ...]:
    """Name the transform contract and source adapters that materialize AtlasFeatures."""
    if type(feature_schema) is not FeatureSchema:
        _invalid("BAMF_C09_ATLAS_FEATURE_OWNER_INVALID")
    schema_contract = contract_digest((
        feature_schema.schema_version,
        feature_schema.role_ids,
        feature_schema.schema_ids,
        feature_schema.source_bindings,
    ))
    return tuple(sorted({
        DependencyRef(
            DependencyKind.OPERATOR,
            "operator:" + FEATURE_MANIFEST_OPERATOR_ID,
        ),
        DependencyRef(
            DependencyKind.OPERATOR,
            "operator:atlas-feature-schema:" + schema_contract,
        ),
        *(DependencyRef(
            DependencyKind.OPERATOR,
            "operator:" + adapter_id,
        ) for _schema_id, adapter_id in feature_schema.source_bindings),
    }))


def _node(
    features: AtlasFeatures,
    predecessor: AtlasFeatures | None,
    feature_schema: FeatureSchema | None = None,
) -> ArtifactNode:
    dependencies = [_source_ref(features), _release_ref(features), _atlas_ref(features)]
    if feature_schema is not None:
        dependencies.extend(_feature_schema_refs(feature_schema))
    if predecessor is not None:
        dependencies.append(DependencyRef(DependencyKind.ARTIFACT, _artifact_id(predecessor)))
    impact, exigency = owner_priority(ArtifactKind.ATLAS_FEATURE)
    return ArtifactNode(
        artifact_id=_artifact_id(features),
        kind=ArtifactKind.ATLAS_FEATURE,
        content_digest=features.digest,
        eligible=True,
        immediate_dependencies=tuple(sorted(dependencies)),
        impact=impact,
        exigency=exigency,
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
        self._index = DependencyIndex.build((
            *nodes,
            _node(features, predecessor, feature_schema),
        ))
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
    def index(self) -> DependencyIndex:
        return self._index

    def _install_context_revalidation(
        self, index: DependencyIndex, transition,
    ) -> bool:
        if (not isinstance(index, DependencyIndex)
                or {node.artifact_id for node in index.nodes}
                != {node.artifact_id for node in self._index.nodes}):
            _invalid("BAMF_C09_CONTEXT_REVALIDATION_INDEX_DRIFT")
        self._index = index

    @property
    def queue(self) -> RevalidationQueue | None:
        return self._queue

    def require(self, features: AtlasFeatures) -> ArtifactNode:
        if type(features) is not AtlasFeatures or _artifact_id(features) != self._current_artifact_id:
            _invalid("BAMF_C09_ATLAS_FEATURE_OWNER_MISMATCH")
        node = self.current_node
        if node.content_digest != features.digest:
            _invalid("BAMF_C09_ATLAS_FEATURE_CONTENT_DRIFT")
        from bilqis_mlx.runtime.accepted_correction_runtime import require_pending_corrections
        require_pending_corrections(self, node.artifact_id)
        if self._queue is not None:
            return read_artifact(self._index, self._queue, node.artifact_id)
        if not node.eligible:
            _invalid("BAMF_C09_ARTIFACT_INELIGIBLE")
        return node

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
