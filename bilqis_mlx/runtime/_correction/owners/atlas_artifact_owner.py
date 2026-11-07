"""Production-owned C09 dependency state for released Atlas features."""
from __future__ import annotations

from bilqis_mlx.semantics.atlas_features import AtlasFeatures, FeatureSchema
from bilqis_mlx.semantics.frame_compiler import CompiledFrameBatch, CompiledFrameRows
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
    def index(self) -> DependencyIndex:
        return self._index

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



def _context_time_ref(row: CompiledFrameBatch, packed, config) -> DependencyRef | None:
    """Bind source-validity boundaries without treating wall-clock ticks as changes."""
    from bilqis_mlx.semantics.frame_compiler import FrameCompilerConfig
    if type(config) is not FrameCompilerConfig:
        _invalid("BAMF_C09_PACKED_FRAME_TEMPORAL_CONTEXT_INVALID")
    if config.approved is None:
        return None
    envelope = next((
        item for item in config.approved.envelopes
        if item.frame.occurrence_id == packed.sidecar.occurrence_id
    ), None)
    if envelope is None:
        _invalid("BAMF_C09_PACKED_FRAME_TEMPORAL_CONTEXT_INVALID")
    handles = {
        envelope.source_handle,
        *(member.source_handle for member in envelope.members),
    }
    grants = tuple(
        grant for grant in config.frontier.grants
        if grant.source_handle in handles)
    if not grants:
        return None
    effective_boundaries = tuple(sorted({
        boundary for grant in grants
        for boundary in (grant.effective_from, grant.effective_until)
        if boundary is not None
    }))
    observed_boundaries = tuple(sorted({grant.observed_at for grant in grants}))
    key = contract_digest({
        "scope": row.scope,
        "sources": tuple(sorted(grant.source_handle for grant in grants)),
        "effective_boundaries": effective_boundaries,
        "effective_bucket": sum(
            boundary <= config.task.effective_time for boundary in effective_boundaries),
        "observed_boundaries": observed_boundaries,
        "observed_bucket": sum(
            boundary <= config.task.observed_frontier for boundary in observed_boundaries),
    })
    return DependencyRef(DependencyKind.TIME, "time:context-boundary:" + key)


def _packed_frame_node(row: CompiledFrameBatch, packed, config=None) -> ArtifactNode:
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
            DependencyKind.POLICY,
            "policy:" + contract_digest((row.scope, row.policy_version[0], row.policy_version[1]))),
        DependencyRef(
            DependencyKind.RIGHTS,
            "rights:" + contract_digest((row.policy_version[2], row.policy_version[3]))),
    ))
    if config is not None:
        time_ref = _context_time_ref(row, packed, config)
        if time_ref is not None:
            dependencies.add(time_ref)
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


class PackedFrameArtifactOwner:
    """Own correction state for actual A05 PackedFrame objects consumed by B03."""

    def __init__(self, rows: CompiledFrameRows, configs=()):
        if (type(rows) is not CompiledFrameRows or not rows.rows
                or type(configs) is not tuple
                or (configs and len(configs) != len(rows.rows))):
            _invalid("BAMF_C09_PACKED_FRAME_OWNER_INVALID")
        self._rows = rows
        self._configs = configs
        self._temporal_holds = set()
        nodes = {}
        for index, row in enumerate(rows.rows):
            config = configs[index] if configs else None
            for position in row.positions:
                if position.packed is None:
                    continue
                node = _packed_frame_node(row, position.packed, config)
                prior = nodes.get(node.artifact_id)
                if prior is not None and prior != node:
                    _invalid("BAMF_C09_PACKED_FRAME_IDENTITY_DRIFT")
                nodes[node.artifact_id] = node
        self._index = DependencyIndex.build(tuple(nodes.values()))
        self._queue: RevalidationQueue | None = None

    @property
    def index(self) -> DependencyIndex:
        return self._index

    @property
    def queue(self) -> RevalidationQueue | None:
        return self._queue

    def node_for(self, packed) -> ArtifactNode:
        from bilqis_mlx.semantics.frame_codec import PackedFrame
        if type(packed) is not PackedFrame:
            _invalid("BAMF_C09_PACKED_FRAME_OWNER_INVALID")
        return self._index.node("frame:" + packed.sidecar.occurrence_id)

    def require_row(self, row: CompiledFrameBatch, config=None) -> tuple[ArtifactNode, ...]:
        if type(row) is not CompiledFrameBatch or row not in self._rows.rows:
            _invalid("BAMF_C09_PACKED_FRAME_OWNER_MISMATCH")
        result = []
        for position in row.positions:
            if position.packed is None:
                continue
            expected = _packed_frame_node(row, position.packed, config)
            node = self.node_for(position.packed)
            if node.content_digest != expected.content_digest:
                _invalid("BAMF_C09_PACKED_FRAME_CONTENT_DRIFT")
            if node.immediate_dependencies != expected.immediate_dependencies:
                prior_time = tuple(ref for ref in node.immediate_dependencies
                                   if ref.kind is DependencyKind.TIME)
                current_time = tuple(ref for ref in expected.immediate_dependencies
                                     if ref.kind is DependencyKind.TIME)
                if (prior_time != current_time
                        and tuple(ref for ref in node.immediate_dependencies
                                 if ref.kind is not DependencyKind.TIME)
                        == tuple(ref for ref in expected.immediate_dependencies
                                 if ref.kind is not DependencyKind.TIME)):
                    self._temporal_holds.add(node.artifact_id)
                else:
                    _invalid("BAMF_C09_PACKED_FRAME_CONTENT_DRIFT")
            from bilqis_mlx.runtime.accepted_correction_runtime import require_pending_corrections
            require_pending_corrections(self, node.artifact_id)
            if node.artifact_id in self._temporal_holds:
                _invalid("BAMF_C09_ARTIFACT_HELD")
            if self._queue is not None:
                node = read_artifact(self._index, self._queue, node.artifact_id)
            elif not node.eligible:
                _invalid("BAMF_C09_ARTIFACT_INELIGIBLE")
            result.append(node)
        return tuple(result)

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
