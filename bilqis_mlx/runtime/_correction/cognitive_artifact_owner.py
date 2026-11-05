"""Production C09 ownership for exact cache, compositions and learned support."""
from __future__ import annotations

from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex, DependencyKind, DependencyRef,
)
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.runtime._revalidation_base import _invalid


def _source_key(value: str) -> str:
    return value if value.startswith("source:") else "source:" + value


def _source_refs(values) -> tuple[DependencyRef, ...]:
    return tuple(sorted({
        DependencyRef(DependencyKind.SOURCE, _source_key(value))
        for value in values if isinstance(value, str) and value
    }))


def _composition_dependencies(composition, binding) -> tuple[DependencyRef, ...]:
    source_handles: set[str] = set()
    operators: set[str] = set()
    for node in composition.goal.expression_or_holes.nodes:
        operators.update(
            (node.operator_id,) if node.operator_id is not None
            else node.candidate_operator_ids)
        for ref in node.operands:
            if ref is None or ref.kind.value == "RESULT":
                continue
            if ref.kind.value == "LITERAL":
                source_handles.add(ref.source_handle)
                continue
            envelope = next(
                item for item in binding.frames if item.frame_handle == ref.frame_handle)
            source_handles.add(envelope.source_handle)
            member = next(
                item for item in envelope.members
                if (item.role_id, item.occurrence_index)
                == (ref.role_id, ref.occurrence_index))
            source_handles.add(member.source_handle)
    refs = set(_source_refs(source_handles))
    refs.update(
        DependencyRef(DependencyKind.OPERATOR, "operator:" + operator_id)
        for operator_id in operators)
    refs.update((
        DependencyRef(
            DependencyKind.RELEASE,
            "release:" + composition.goal.semantic_release),
        DependencyRef(
            DependencyKind.POLICY,
            "policy:qualification:" + composition.qualification_receipt_sha256),
        DependencyRef(
            DependencyKind.RIGHTS,
            "rights:" + contract_digest((
                composition.rights_epoch, composition.correction_generation))),
        DependencyRef(
            DependencyKind.TIME,
            "time:task:" + contract_digest(binding.task)),
    ))
    return tuple(sorted(refs))


class CognitiveArtifactOwner:
    """Retain C09 correction state for real C04/C05 materializations."""

    def __init__(self):
        self._index = DependencyIndex.build(())
        self._queue = None
        self._active_task_sha256: str | None = None
        self._active_support: set[str] | None = None
        self._result_support: dict[str, tuple[str, ...]] = {}
        self._capability_ledgers: dict[str, object] = {}

    @property
    def index(self) -> DependencyIndex:
        return self._index

    @property
    def queue(self):
        return self._queue

    def _add(self, node: ArtifactNode) -> ArtifactNode:
        existing = next(
            (item for item in self._index.nodes if item.artifact_id == node.artifact_id),
            None,
        )
        if existing is not None:
            if existing != node:
                _invalid("BAMF_C09_ARTIFACT_NODE_INVALID")
            return existing
        self._index = DependencyIndex.build((*self._index.nodes, node))
        return node

    def _require(self, expected: ArtifactNode) -> ArtifactNode:
        node = self._index.node(expected.artifact_id)
        if (node.kind is not expected.kind
                or node.content_digest != expected.content_digest
                or node.immediate_dependencies != expected.immediate_dependencies):
            _invalid("BAMF_C09_ARTIFACT_INELIGIBLE")
        if self._queue is not None:
            from bilqis_mlx.runtime._revalidation_engine import read_artifact
            return read_artifact(self._index, self._queue, node.artifact_id)
        if not node.eligible:
            _invalid("BAMF_C09_ARTIFACT_INELIGIBLE")
        return node

    def _remember(self, task_sha256: str | None, artifact_id: str) -> None:
        if task_sha256 is None:
            return
        if (self._active_support is None
                or task_sha256 != self._active_task_sha256):
            _invalid("BAMF_C09_SUPPORT_SCOPE_INVALID")
        self._active_support.add(artifact_id)

    def begin_evaluation(self, task_sha256: str) -> None:
        if (not isinstance(task_sha256, str) or not task_sha256
                or self._active_support is not None):
            _invalid("BAMF_C09_SUPPORT_SCOPE_INVALID")
        self._active_task_sha256 = task_sha256
        self._active_support = set()

    def active_support(self, task_sha256: str) -> tuple[str, ...]:
        if (self._active_support is None
                or task_sha256 != self._active_task_sha256):
            _invalid("BAMF_C09_SUPPORT_SCOPE_INVALID")
        return tuple(sorted(self._active_support))

    def finish_evaluation(self, result) -> tuple[str, ...]:
        if self._active_support is None:
            _invalid("BAMF_C09_SUPPORT_SCOPE_INVALID")
        support = tuple(sorted(self._active_support))
        result_digest = contract_digest(result.replay_record())
        existing = self._result_support.get(result_digest)
        if existing is not None and existing != support:
            _invalid("BAMF_C09_SUPPORT_RESULT_DRIFT")
        self._result_support[result_digest] = support
        self._active_task_sha256 = None
        self._active_support = None
        return support

    def abort_evaluation(self) -> None:
        self._active_task_sha256 = None
        self._active_support = None

    def support_for_result(self, result) -> tuple[str, ...]:
        try:
            return self._result_support[contract_digest(result.replay_record())]
        except KeyError:
            _invalid("BAMF_C09_SUPPORT_RESULT_MISSING")

    def bind_capability_ledger(self, assessment_digest: str, ledger) -> None:
        if not isinstance(assessment_digest, str) or not assessment_digest:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_INVALID")
        existing = self._capability_ledgers.get(assessment_digest)
        if existing is not None and existing != ledger:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_INVALID")
        self._capability_ledgers[assessment_digest] = ledger

    def capability_ledger(self, assessment_digest: str):
        try:
            return self._capability_ledgers[assessment_digest]
        except KeyError:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_INVALID")

    def exact_cache_node(
        self, *, key: str, content_digest: str, source_handles: tuple[str, ...],
        predecessor_keys: tuple[str, ...], operator_id: str,
        semantic_release: str, policy_digest: str, rights_digest: str,
        time_digest: str,
    ) -> ArtifactNode:
        refs = set(_source_refs(source_handles))
        refs.update(
            DependencyRef(DependencyKind.ARTIFACT, "cache:" + predecessor)
            for predecessor in predecessor_keys)
        refs.update((
            DependencyRef(DependencyKind.OPERATOR, "operator:" + operator_id),
            DependencyRef(DependencyKind.RELEASE, "release:" + semantic_release),
            DependencyRef(DependencyKind.POLICY, "policy:" + policy_digest),
            DependencyRef(DependencyKind.RIGHTS, "rights:" + rights_digest),
            DependencyRef(DependencyKind.TIME, "time:task:" + time_digest),
        ))
        return ArtifactNode(
            artifact_id="cache:" + key,
            kind=ArtifactKind.EXACT_CACHE,
            content_digest=content_digest,
            eligible=True,
            immediate_dependencies=tuple(sorted(refs)),
            impact=3,
            exigency=4,
        )

    def materialize_exact_cache(self, *, task_sha256: str | None = None, **kwargs):
        node = self._add(self.exact_cache_node(**kwargs))
        self._remember(task_sha256, node.artifact_id)
        return node

    def require_exact_cache(
        self, *, task_sha256: str | None = None, **kwargs,
    ) -> ArtifactNode:
        node = self._require(self.exact_cache_node(**kwargs))
        self._remember(task_sha256, node.artifact_id)
        return node

    def composition_node(
        self, composition, binding, support_artifact_ids=(),
    ) -> ArtifactNode:
        digest = contract_digest(composition)
        refs = set(_composition_dependencies(composition, binding))
        refs.update(
            DependencyRef(DependencyKind.ARTIFACT, artifact_id)
            for artifact_id in support_artifact_ids)
        return ArtifactNode(
            artifact_id="composition:" + digest,
            kind=ArtifactKind.OPERATOR_COMPOSITION,
            content_digest=digest,
            eligible=True,
            immediate_dependencies=tuple(sorted(refs)),
            impact=3,
            exigency=3,
        )

    def materialize_composition(
        self, composition, binding, task_sha256: str | None = None,
        support_artifact_ids=(),
    ) -> ArtifactNode:
        node = self._add(self.composition_node(
            composition, binding, support_artifact_ids))
        self._remember(task_sha256, node.artifact_id)
        return node

    def require_composition(
        self, composition, binding, task_sha256: str | None = None,
    ) -> ArtifactNode:
        expected_id = "composition:" + contract_digest(composition)
        node = self._index.node(expected_id)
        if (node.kind is not ArtifactKind.OPERATOR_COMPOSITION
                or node.content_digest != contract_digest(composition)):
            _invalid("BAMF_C09_ARTIFACT_INELIGIBLE")
        if self._queue is not None:
            from bilqis_mlx.runtime._revalidation_engine import read_artifact
            node = read_artifact(self._index, self._queue, expected_id)
        elif not node.eligible:
            _invalid("BAMF_C09_ARTIFACT_INELIGIBLE")
        self._remember(task_sha256, node.artifact_id)
        return node

    def has_composition(self, composition) -> bool:
        artifact_id = "composition:" + contract_digest(composition)
        return any(node.artifact_id == artifact_id for node in self._index.nodes)

    def materialize_capability_support(self, support, history_sha256: str) -> ArtifactNode:
        refs = {
            DependencyRef(DependencyKind.ARTIFACT, artifact_id)
            for artifact_id in support.support_artifact_ids
        }
        refs.update(_source_refs(support.source_anchor_ids))
        refs.add(DependencyRef(DependencyKind.SOURCE, "history:" + history_sha256))
        node = ArtifactNode(
            artifact_id="capability:" + contract_digest((support, history_sha256)),
            kind=ArtifactKind.CAPABILITY_SUPPORT,
            content_digest=contract_digest(support),
            eligible=support.status.value == "QUALIFIED",
            immediate_dependencies=tuple(sorted(refs)),
            impact=4,
            exigency=2,
        )
        return self._add(node)

    def apply_correction(
        self, event, authority_registry,
    ):
        from bilqis_mlx.runtime._revalidation_engine import apply_correction
        self._queue = apply_correction(event, self._index, authority_registry)
        if self._capability_ledgers:
            from bilqis_mlx.runtime.atlas_requalification import (
                mark_affected_capabilities,
            )
            self._capability_ledgers = {
                assessment_digest: mark_affected_capabilities(
                    ledger, self._index, self._queue).ledger
                for assessment_digest, ledger in self._capability_ledgers.items()
            }
        return self._queue

    def advance(
        self, frontier, authority_registry,
    ):
        from bilqis_mlx.runtime._revalidation_engine import (
            advance_revalidation, next_revalidation_task, revalidate_node,
        )
        if self._queue is None:
            _invalid("BAMF_C09_REVALIDATION_ARGUMENT_INVALID")
        task = next_revalidation_task(self._index, self._queue)
        if task is None:
            _invalid("BAMF_C09_REVALIDATION_EVIDENCE_MISSING")
        transition = revalidate_node(
            self._index.node(task.artifact_id), frontier, authority_registry)
        progress = advance_revalidation(
            self._index, self._queue, transition, authority_registry)
        self._index = progress.index
        self._queue = progress.queue
        return progress
