"""C09 correction ownership for C04 reusable qualified operator compositions."""
from __future__ import annotations

from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex, DependencyKind, DependencyRef,
)
from bilqis_mlx.semantics.cognitive_operators import OperatorBinding
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.runtime.atlas_revalidation_common import _invalid, owner_priority
from bilqis_mlx.runtime.atlas_revalidation_evidence import (
    CorrectionEvent, RevalidationFrontier,
)
from bilqis_mlx.runtime.atlas_revalidation_queue import (
    RevalidationProgress, RevalidationQueue, _sort_tasks, _task,
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
    policy_ref = DependencyRef(
        DependencyKind.POLICY,
        "policy:" + contract_digest((
            binding.task.scope,
            binding.policy.policy_id,
            binding.policy.policy_epoch,
        )),
    )
    rights_ref = DependencyRef(
        DependencyKind.RIGHTS,
        "rights:" + contract_digest((
            binding.policy.rights_epoch,
            binding.frontier.correction_generation,
        )),
    )
    dependencies = {
        DependencyRef(DependencyKind.SOURCE, "source:binding:" + binding_digest),
        DependencyRef(DependencyKind.SOURCE, "source:qualification:" + composition.qualification_receipt_sha256),
        *(DependencyRef(DependencyKind.SOURCE, operand.source_reference)
          for operand in binding.operands),
        DependencyRef(DependencyKind.RELEASE, "generation:" + composition.generation_digest),
        DependencyRef(DependencyKind.RELEASE, "semantic-release:" + composition.goal.semantic_release),
        DependencyRef(DependencyKind.RIGHTS, "rights-epoch:" + str(composition.rights_epoch)),
        rights_ref,
        DependencyRef(DependencyKind.POLICY, "correction-generation:" + str(composition.correction_generation)),
        policy_ref,
        DependencyRef(
            DependencyKind.TIME,
            "time:observed-frontier:" + str(binding.task.observed_frontier)),
        DependencyRef(
            DependencyKind.TIME,
            "time:effective:" + str(binding.task.effective_time)),
        DependencyRef(
            DependencyKind.TIME,
            "time:causal-prefix-end:" + str(binding.task.causal_prefix_end)),
        *(DependencyRef(DependencyKind.OPERATOR, "operator:" + operator_id)
          for operator_id in composition.goal.allowed_operator_ids),
    }
    if binding.frames:
        from bilqis_mlx.semantics.context_eligibility import (
            ApprovedContextProjection, project_context,
        )
        projection = project_context(
            binding.frames, binding.task, binding.frontier, binding.policy)
        if isinstance(projection, ApprovedContextProjection):
            dependencies.add(DependencyRef(
                DependencyKind.TIME,
                "time:asof:context:" + projection.digest,
            ))
    impact, exigency = owner_priority(ArtifactKind.OPERATOR_COMPOSITION)
    return ArtifactNode(
        artifact_id="composition:" + composition.qualification_receipt_sha256,
        kind=ArtifactKind.OPERATOR_COMPOSITION,
        content_digest=contract_digest(composition),
        eligible=True,
        immediate_dependencies=tuple(sorted(dependencies)),
        impact=impact,
        exigency=exigency,
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

    def _install_context_revalidation(
        self, index: DependencyIndex, transition,
    ) -> bool:
        if (not isinstance(index, DependencyIndex)
                or {node.artifact_id for node in index.nodes}
                != {node.artifact_id for node in self._index.nodes}):
            _invalid("BAMF_C09_CONTEXT_REVALIDATION_INDEX_DRIFT")
        if transition.new_dependencies != transition.previous_dependencies:
            # The binding is the physical authority for a qualified composition.
            # A new context therefore requires a newly materialized binding rather
            # than rewriting dependency metadata under the old composition.
            return False
        self._index = index
        return True

    @property
    def queue(self) -> RevalidationQueue | None:
        return self._queue

    @property
    def compositions(self) -> tuple:
        return tuple(
            self._compositions[key] for key in sorted(self._cache_keys))

    def is_materialized(self, composition) -> bool:
        return composition.qualification_receipt_sha256 in self._materialized

    def remember(
        self, composition, binding: OperatorBinding, *,
        max_cached_candidates: int | None = None,
    ) -> bool:
        """Retain one composition only after the live solver validated it."""
        node = _node(composition, binding)
        key = composition.qualification_receipt_sha256
        existing = self._compositions.get(key)
        if existing is not None and existing != composition:
            _invalid("BAMF_C09_OPERATOR_COMPOSITION_RECEIPT_COLLISION")
        if (existing is None and max_cached_candidates is not None
                and len(self._cache_keys) >= max_cached_candidates):
            return False
        self._compositions[key] = composition
        self._cache_keys.add(key)
        self._materialized.add(key)
        existing_nodes = {
            existing_node.artifact_id: existing_node
            for existing_node in self._index.nodes
        }
        rebuilt = []
        for composition_key in sorted(self._compositions):
            expected = _node(self._compositions[composition_key], binding)
            prior = existing_nodes.get(expected.artifact_id)
            if prior is not None:
                if (prior.content_digest != expected.content_digest
                        or prior.immediate_dependencies
                        != expected.immediate_dependencies):
                    _invalid("BAMF_C09_OPERATOR_COMPOSITION_CONTENT_DRIFT")
                rebuilt.append(prior)
            else:
                rebuilt.append(expected)
        self._index = DependencyIndex.build(tuple(rebuilt))
        if (self._queue is not None
                and node.artifact_id not in self._queue.held_artifact_ids
                and self._queue.event.dependency in node.immediate_dependencies):
            history_ids = {item.artifact_id for item in self._queue.history}
            if node.artifact_id not in history_ids:
                pending = _sort_tasks((*self._queue.pending, _task(
                    self._index.node(node.artifact_id),
                    self._queue.event.dependency,
                )))
                self._queue = RevalidationQueue(
                    self._queue.event,
                    pending,
                    tuple(sorted(item.artifact_id for item in pending)),
                    self._queue.history,
                )
        from bilqis_mlx.runtime.accepted_correction_runtime import (
            refresh_owner_corrections,
        )
        refresh_owner_corrections(self)
        return True

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
        from bilqis_mlx.runtime.accepted_correction_runtime import (
            require_pending_corrections,
        )
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

    def hold_late_correction(
        self, event: CorrectionEvent, artifact_ids: tuple[str, ...],
        authority_registry: SourceAuthorityRegistry,
    ) -> RevalidationQueue:
        """Hold only compositions materialized after this branch was reconciled."""
        if (not isinstance(event, CorrectionEvent)
                or not isinstance(artifact_ids, tuple)
                or not artifact_ids
                or artifact_ids != tuple(sorted(set(artifact_ids)))
                or not isinstance(authority_registry, SourceAuthorityRegistry)):
            _invalid("BAMF_C09_OPERATOR_COMPOSITION_LATE_HOLD_INVALID")
        authority_registry.verify_correction(event)
        tasks = []
        for artifact_id in artifact_ids:
            node = self._index.node(artifact_id)
            if event.dependency not in node.immediate_dependencies:
                _invalid("BAMF_C09_OPERATOR_COMPOSITION_LATE_HOLD_DRIFT")
            tasks.append(_task(node, event.dependency))
        if self._queue is not None and self._queue.pending:
            if self._queue.event.event_id != event.event_id:
                _invalid("BAMF_C09_OPERATOR_COMPOSITION_LATE_HOLD_BUSY")
            history_ids = {
                transition.artifact_id for transition in self._queue.history}
            pending_by_id = {
                task.artifact_id: task for task in self._queue.pending}
            for task in tasks:
                if task.artifact_id not in history_ids:
                    pending_by_id.setdefault(task.artifact_id, task)
            pending = _sort_tasks(tuple(pending_by_id.values()))
            self._queue = RevalidationQueue(
                event, pending,
                tuple(sorted(task.artifact_id for task in pending)),
                self._queue.history,
            )
            return self._queue
        pending = _sort_tasks(tuple(tasks))
        self._queue = RevalidationQueue(
            event, pending,
            tuple(sorted(task.artifact_id for task in pending)),
        )
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
