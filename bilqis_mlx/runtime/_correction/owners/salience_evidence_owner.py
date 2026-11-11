"""C09 dependency ownership for exact signed C06 labels and source rights."""
from __future__ import annotations

from dataclasses import replace

from bilqis_mlx.learning.atlas_salience import derive_salience, verify_salience_inputs
from bilqis_mlx.learning.salience_contracts import FactOrigin
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex, DependencyKind, DependencyRef,
)
from bilqis_mlx.semantics.domains import contract_digest
from .atlas_revalidation_common import _invalid, owner_priority
from .atlas_revalidation_runtime import (
    advance_revalidation, apply_correction, next_revalidation_task, read_artifact,
    revalidate_node,
)


def _evidence_index(records, row_dependencies):
    dependencies = dict(row_dependencies)
    nodes = {}
    roots = []
    priority = owner_priority(ArtifactKind.SALIENCE_EVIDENCE)

    def add(identity, content, parents, context):
        node = ArtifactNode(identity, ArtifactKind.SALIENCE_EVIDENCE,
            contract_digest(content), True, tuple(sorted(set((*context, *parents)))), *priority)
        previous = nodes.get(identity)
        if previous is not None:
            if previous.content_digest != node.content_digest:
                _invalid('BAMF_SALIENCE_EVIDENCE_NODE_DIVERGENCE')
            node = replace(node, immediate_dependencies=tuple(sorted(set(
                (*previous.immediate_dependencies, *node.immediate_dependencies)))))
        nodes[identity] = node
        return node.reference

    for binding, evidence in records:
        basis = evidence.basis
        verified = verify_salience_inputs(basis.facts, basis.policy, basis.snapshot, basis.context)
        if derive_salience(verified) != evidence or binding.salience_inputs_digest != basis.digest():
            _invalid('BAMF_SALIENCE_ROW_LABEL_EVIDENCE_DRIFT')
        context = dependencies.get(binding.row_id)
        if not context or any(ref.kind is DependencyKind.ARTIFACT for ref in context):
            _invalid('BAMF_SALIENCE_ROW_DEPENDENCIES_INVALID')
        # Shared signed facts retain their public correction identity across rows.
        policy = add('salience-policy:' + basis.policy.digest(), basis.policy,
            (DependencyRef(DependencyKind.POLICY, 'salience-policy:' + basis.policy.policy_id),), context)
        facts = []
        for fact in basis.facts:
            parents = (policy,)
            if fact.origin is FactOrigin.SOURCE:
                parents += (DependencyRef(DependencyKind.SOURCE, 'salience-fact:' + fact.fact_id),)
            facts.append(add('salience-fact:' + fact.fact_id, fact, parents, context))
        roots.append(add('salience-row:' + binding.row_id, binding, (policy, *facts), context))
    if not roots:
        _invalid('BAMF_SALIENCE_ROW_RECORDS_REQUIRED')
    context = tuple(sorted({ref for refs in dependencies.values() for ref in refs}))
    digest = contract_digest((records, row_dependencies))
    root = add('salience-labels:' + digest, (records, row_dependencies), roots, context)
    return DependencyIndex.build(tuple(nodes.values())), root.key


class SalienceEvidenceArtifactOwner:
    """Hold signed auxiliary evidence when its actual source inputs change."""

    def __init__(self, records, row_dependencies):
        self._index, self._artifact_id = _evidence_index(records, row_dependencies)
        self._queue = None
        self._context_changed = False

    @property
    def index(self):
        return self._index

    @property
    def current_node(self):
        return self._index.node(self._artifact_id)

    @property
    def queue(self):
        return self._queue

    def require(self):
        from .accepted_correction_runtime import require_pending_corrections
        if self._context_changed:
            _invalid('BAMF_SALIENCE_CONTEXT_REPREPARATION_REQUIRED')
        for node in self.index.nodes:
            require_pending_corrections(self, node.artifact_id)
            if self._queue is not None:
                read_artifact(self.index, self._queue, node.artifact_id)
            elif not node.eligible:
                _invalid('BAMF_C09_ARTIFACT_INELIGIBLE')
        return self.current_node

    def _install_context_revalidation(self, index, transition):
        if (not isinstance(index, DependencyIndex)
                or {node.artifact_id for node in index.nodes}
                != {node.artifact_id for node in self.index.nodes}):
            _invalid('BAMF_SALIENCE_CONTEXT_INDEX_DRIFT')
        self._index = index
        self._context_changed |= transition.changed
        return True

    def apply_correction(self, event, authority_registry):
        from .accepted_correction_runtime import require_bound_owner_registry
        registry = require_bound_owner_registry(self, authority_registry)
        self._queue = apply_correction(event, self.index, registry)
        return self._queue

    def advance(self, frontier, authority_registry):
        from .accepted_correction_runtime import require_bound_owner_registry
        registry = require_bound_owner_registry(self, authority_registry)
        if self._queue is None:
            _invalid('BAMF_C09_REVALIDATION_NOT_HELD')
        task = next_revalidation_task(self.index, self._queue)
        if task is None:
            _invalid('BAMF_C09_REVALIDATION_NOT_PENDING')
        transition = revalidate_node(self.index.node(task.artifact_id), frontier, registry)
        progress = advance_revalidation(self.index, self._queue, transition, registry)
        self._index, self._queue = progress.index, progress.queue
        if transition.changed:
            self._context_changed = True
        return progress
