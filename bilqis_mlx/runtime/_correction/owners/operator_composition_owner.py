"""C09 correction ownership for C04 reusable qualified operator compositions."""
from __future__ import annotations

from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex, DependencyKind, DependencyRef,
)
from bilqis_mlx.semantics.cognitive_operators import OperatorBinding
from bilqis_mlx.semantics.domains import contract_digest
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


def _node(composition, binding: OperatorBinding) -> ArtifactNode:
    from bilqis_mlx.runtime.cognitive_solver import QualifiedComposition
    if type(composition) is not QualifiedComposition or type(binding) is not OperatorBinding:
        _invalid("BAMF_C09_OPERATOR_COMPOSITION_OWNER_INVALID")
    binding_digest = contract_digest(binding)
    if composition.source_binding_digest != binding_digest:
        _invalid("BAMF_C09_OPERATOR_COMPOSITION_SOURCE_DRIFT")
    dependencies = {
        DependencyRef(DependencyKind.SOURCE, "source:binding:" + binding_digest),
        DependencyRef(DependencyKind.SOURCE, "source:qualification:" + composition.qualification_receipt_sha256),
        DependencyRef(DependencyKind.RELEASE, "semantic-release:" + composition.goal.semantic_release),
        DependencyRef(DependencyKind.RIGHTS, "rights-epoch:" + str(composition.rights_epoch)),
        DependencyRef(DependencyKind.POLICY, "correction-generation:" + str(composition.correction_generation)),
        *(DependencyRef(DependencyKind.OPERATOR, "operator:" + operator_id)
          for operator_id in composition.goal.allowed_operator_ids),
    }
    return ArtifactNode(
        artifact_id="composition:" + composition.qualification_receipt_sha256,
        kind=ArtifactKind.OPERATOR_COMPOSITION,
        content_digest=contract_digest(composition),
        eligible=True,
        immediate_dependencies=tuple(sorted(dependencies)),
        impact=0,
        exigency=0,
    )


class OperatorCompositionArtifactOwner:
    """Retain correction holds across repeated Factory solver calls."""

    def __init__(self, binding: OperatorBinding, compositions: tuple, fallback=None):
        if type(binding) is not OperatorBinding or type(compositions) is not tuple:
            _invalid("BAMF_C09_OPERATOR_COMPOSITION_OWNER_INVALID")
        self._binding_digest = contract_digest(binding)
        owned = (*compositions, *((fallback,) if fallback is not None else ()))
        self._compositions = {
            item.qualification_receipt_sha256: item for item in owned}
        self._cache_keys = {
            item.qualification_receipt_sha256 for item in compositions}
        self._materialized: set[str] = set()
        nodes = tuple(_node(item, binding) for item in owned)
        self._index = DependencyIndex.build(nodes)
        self._queue: RevalidationQueue | None = None

    @property
    def index(self) -> DependencyIndex:
        return self._index

    @property
    def queue(self) -> RevalidationQueue | None:
        return self._queue

    @property
    def compositions(self) -> tuple:
        return tuple(
            self._compositions[key] for key in sorted(self._cache_keys))

    def is_materialized(self, composition) -> bool:
        return composition.qualification_receipt_sha256 in self._materialized

    def remember(self, composition, binding: OperatorBinding) -> None:
        """Retain one composition only after the live solver validated it."""
        node = _node(composition, binding)
        key = composition.qualification_receipt_sha256
        existing = self._compositions.get(key)
        if existing is not None and existing != composition:
            _invalid("BAMF_C09_OPERATOR_COMPOSITION_RECEIPT_COLLISION")
        self._compositions[key] = composition
        self._cache_keys.add(key)
        self._materialized.add(key)
        self._index = DependencyIndex.build(tuple(
            _node(self._compositions[key], binding)
            for key in sorted(self._compositions)))

    def node_for(self, composition) -> ArtifactNode:
        return self._index.node("composition:" + composition.qualification_receipt_sha256)

    def require(self, composition, binding: OperatorBinding) -> ArtifactNode:
        if contract_digest(binding) != self._binding_digest:
            _invalid("BAMF_C09_OPERATOR_COMPOSITION_BINDING_DRIFT")
        expected = _node(composition, binding)
        node = self.node_for(composition)
        if (node.content_digest != expected.content_digest
                or node.immediate_dependencies != expected.immediate_dependencies):
            _invalid("BAMF_C09_OPERATOR_COMPOSITION_CONTENT_DRIFT")
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
            _invalid("BAMF_C09_OPERATOR_COMPOSITION_REVALIDATION_NOT_HELD")
        task = next_revalidation_task(self._index, self._queue)
        if task is None:
            _invalid("BAMF_C09_OPERATOR_COMPOSITION_REVALIDATION_NOT_PENDING")
        transition = revalidate_node(
            self._index.node(task.artifact_id), frontier, authority_registry)
        progress = advance_revalidation(
            self._index, self._queue, transition, authority_registry)
        self._index = progress.index
        self._queue = progress.queue
        return progress


__all__ = ("OperatorCompositionArtifactOwner",)
