"""C09 correction ownership for actual B14 exact-cache artifacts."""
from __future__ import annotations

import hashlib

from bilqis_mlx.runtime.atlas_cache_binding import (
    CacheArtifact, CacheBinding, binding_digest, _require_cache_binding,
)
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex, DependencyKind, DependencyRef,
)
from bilqis_mlx.runtime.atlas_source_authority import SourceAuthorityRegistry
from bilqis_mlx.runtime.atlas_revalidation_common import _invalid, owner_priority
from bilqis_mlx.runtime.atlas_revalidation_runtime import (
    advance_revalidation, apply_correction, next_revalidation_task,
    read_artifact, revalidate_node,
)
from bilqis_mlx.runtime.atlas_revalidation_evidence import CorrectionEvent, RevalidationFrontier
from bilqis_mlx.runtime.atlas_revalidation_queue import RevalidationProgress, RevalidationQueue


_ISSUER = object()


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
        artifact.payload_binding_tag or b"",
    ):
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
    return digest.hexdigest()


def _dependencies(binding: CacheBinding) -> tuple[DependencyRef, ...]:
    return tuple(sorted((
        DependencyRef(DependencyKind.RELEASE, "generation:" + binding.generation_sha256),
        DependencyRef(DependencyKind.RELEASE, "source-release:" + binding.source_release_sha256),
        DependencyRef(DependencyKind.RELEASE, "semantic-release:" + binding.semantic_release_sha256),
        DependencyRef(DependencyKind.SOURCE, "lineage:" + binding.lineage_sha256),
        DependencyRef(DependencyKind.OPERATOR, "topology:" + binding.topology_sha256),
        DependencyRef(DependencyKind.RIGHTS, "rights:" + binding.source_rights_sha256),
        DependencyRef(DependencyKind.RIGHTS, "purpose:" + binding.rights_purpose_sha256),
        DependencyRef(DependencyKind.POLICY, "policy-epoch:" + binding.policy_epoch_sha256),
        DependencyRef(DependencyKind.POLICY, "context:" + binding.context_eligibility_sha256),
        DependencyRef(
            DependencyKind.TIME,
            "time:asof:context:" + binding.context_eligibility_sha256),
        DependencyRef(DependencyKind.SOURCE, "prefix:" + binding.causal_prefix_sha256),
        DependencyRef(DependencyKind.POLICY, "masks:" + binding.masks_sha256),
        DependencyRef(DependencyKind.POLICY, "scope:" + binding.scope_sha256),
        DependencyRef(DependencyKind.SOURCE, "key:" + binding.key_sha256),
        DependencyRef(DependencyKind.SOURCE, "inference:" + binding.inference_state_sha256),
        DependencyRef(
            DependencyKind.RIGHTS,
            "artifact-authority:" + binding.artifact_authority_id + ":"
            + binding.artifact_authority_public_key_hex,
        ),
        DependencyRef(DependencyKind.TIME, "offset:" + str(binding.offset)),
    )))


def _node(authority, artifact: CacheArtifact, binding: CacheBinding) -> ArtifactNode:
    from bilqis_mlx.runtime.atlas_cache_eligibility import validate_current_binding
    validate_current_binding(authority, binding)
    _require_cache_binding(artifact, binding, authority)
    impact, exigency = owner_priority(ArtifactKind.EXACT_CACHE)
    return ArtifactNode(
        artifact_id="cache:" + binding_digest(binding).hex(),
        kind=ArtifactKind.EXACT_CACHE,
        content_digest=cache_artifact_digest(artifact),
        eligible=True,
        immediate_dependencies=_dependencies(binding),
        impact=impact,
        exigency=exigency,
    )


class ExactCacheArtifactOwner:
    """Retain correction holds across actual cache reads and recomputation."""

    def __init__(self, *args, **kwargs):
        _invalid("BAMF_C09_EXACT_CACHE_OWNER_CALLER_CONSTRUCTION_FORBIDDEN")

    def _initialize(self, authority, artifact: CacheArtifact, binding: CacheBinding, issuer):
        if issuer is not _ISSUER:
            _invalid("BAMF_C09_EXACT_CACHE_OWNER_ISSUER_INVALID")
        node = _node(authority, artifact, binding)
        self._authority = authority
        self._artifact_id = node.artifact_id
        self._index = DependencyIndex.build((node,))
        self._queue: RevalidationQueue | None = None
        return self

    @property
    def current_node(self) -> ArtifactNode:
        return self._index.node(self._artifact_id)

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
        if transition.new_dependencies != transition.previous_dependencies:
            # Cache identity commits the approved context. Rebinding it in place
            # would make the immutable CacheBinding lie about the stored artifact.
            return False
        self._index = index
        return True

    @property
    def queue(self) -> RevalidationQueue | None:
        return self._queue

    @property
    def rights_dependency(self) -> DependencyRef:
        return next(ref for ref in self.current_node.immediate_dependencies
                    if ref.kind is DependencyKind.RIGHTS)

    def require(self, authority, artifact: CacheArtifact, binding: CacheBinding) -> ArtifactNode:
        if authority is not self._authority:
            _invalid("BAMF_C09_EXACT_CACHE_AUTHORITY_MISMATCH")
        expected = _node(authority, artifact, binding)
        if expected.artifact_id != self._artifact_id:
            _invalid("BAMF_C09_EXACT_CACHE_OWNER_MISMATCH")
        node = self.current_node
        if (node.content_digest != expected.content_digest
                or node.immediate_dependencies != expected.immediate_dependencies):
            _invalid("BAMF_C09_EXACT_CACHE_CONTENT_DRIFT")
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


def _issue_exact_cache_artifact_owner(authority, artifact, binding):
    owner = object.__new__(ExactCacheArtifactOwner)
    return owner._initialize(authority, artifact, binding, _ISSUER)
