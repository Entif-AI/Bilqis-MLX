"""Per-execution compute, verified memo and receipt accounting."""
from __future__ import annotations
from .._public_identity.facade_dependency import public_facade
from ..cognitive_dag import (
    DAGOperand, DAGProgram, DAGBudget, DAGNode, TaskGoal, DAGResult, DAGReceipt,
    OperatorBinding, TypedValue, PureOperationMemo,
)


def _public():
    return public_facade("bilqis_mlx.semantics.cognitive_dag")


_CONTINUE = object()


class _Execution:
    def __init__(
        self, goal, binding, memo, operation_limit, preparation,
        artifact_owner=None, support_task_sha256=None,
    ):
        self.goal = goal
        self.binding = binding
        self.memo = memo
        self.operation_limit = operation_limit
        self.order, self.prepared, self.visible, self.selected, self.unresolved = preparation
        self.program = self.goal.expression_or_holes
        self.compute_limit = (self.goal.budget.max_operations if self.operation_limit is None
                         else self.operation_limit)
        self.release = self.binding.task.semantic_release
        self.source_digest = _public().contract_digest(self.binding)
        self.output_type = next(
            node.expected_output_type for node in self.program.nodes
            if node.node_id == self.program.output_node_id)
        self.computed = 0
        self.lookups = 0
        self.hits = 0
        self.executed: list[str] = []
        self.results: dict[str, _public().TypedValue] = {}
        self.lineage: dict[str, str] = {}
        self.artifact_owner = artifact_owner
        self.support_task_sha256 = support_task_sha256

    def cache_dependencies(self, refs, spec, numeric):
        source_handles = set()
        for ref in refs:
            if ref.kind is _public().RefKind.LITERAL:
                source_handles.add(ref.source_handle)
            elif ref.kind is _public().RefKind.INPUT:
                envelope = next(
                    item for item in self.binding.frames
                    if item.frame_handle == ref.frame_handle)
                source_handles.add(envelope.source_handle)
                member = next(
                    item for item in envelope.members
                    if (item.role_id, item.occurrence_index)
                    == (ref.role_id, ref.occurrence_index))
                source_handles.add(member.source_handle)
        source_handles.add("source:operator:" + spec.operator_id)
        if numeric is not None:
            source_handles.add(self.binding.numeric_source_handle)
        predecessor_keys = tuple(sorted(
            self.lineage[ref.result_node_id]
            for ref in refs if ref.kind is _public().RefKind.RESULT))
        return (
            tuple(sorted(item for item in source_handles if item is not None)),
            predecessor_keys,
            _public().contract_digest(self.binding.policy),
            _public().contract_digest((
                self.binding.frontier.rights_epoch,
                self.binding.frontier.correction_generation)),
        )

    def finish(self, answer: TypedValue, reason: str | None = None) -> DAGResult:
        return _public().DAGResult(answer, _public().DAGReceipt(
            self.release, self.source_digest, self.computed, self.lookups, self.hits,
            self.selected, tuple(self.executed), reason))


    def unresolved_answer(self, node_id: str, type_name: str) -> DAGResult:
        return self.finish(
            _public().TypedValue(self.output_type, None, self.release, state=_public().ValueState.UNRESOLVED),
            node_id + ":" + type_name)


    def step(self, node):
        spec, refs = self.prepared[node.node_id]
        _public()._check_grant(
            "source:operator:" + spec.operator_id,
            _public().operator_grant_digest(spec), self.binding)
        numeric = (
            _public()._number_domain(self.binding)
            if spec.applicability == "FINITE_NUMBER" else None)
        inputs = tuple(
            self.results[ref.result_node_id] if ref.kind is _public().RefKind.RESULT
            else self.visible[ref.identity]
            for ref in refs)
        if any(value.state is not _public().ValueState.VALUE for value in inputs):
            return self.unresolved_answer(node.node_id, node.expected_output_type)
        if (node.operator_id is None
                and _public()._independent_applicability(
                    spec, inputs, self.binding) is False):
            return self.unresolved_answer(node.node_id, node.expected_output_type)
        return self.compute(node, spec, refs, numeric, inputs)


    def compute(self, node, spec, refs, numeric, inputs):
        dependencies = tuple(
            _public()._dependency_record(ref, value, self.binding, self.lineage)
            for ref, value in zip(refs, inputs)) + _public()._consulted_dependencies(
                spec.operator_id, inputs, self.binding)
        authority = (
            self.binding.task, self.binding.policy,
            self.binding.frontier.rights_epoch,
            self.binding.frontier.correction_generation,
            _public()._grant_record("source:operator:" + spec.operator_id, self.binding),
            numeric,
            _public()._grant_record(self.binding.numeric_source_handle, self.binding)
            if numeric is not None else None,
        )
        key = _public().PureOperationMemo.key(
            operator=spec, dependencies=dependencies, authority=authority)
        cached = None
        if self.memo is not None:
            self.lookups += 1
            cached = _public()._memo_get_verified(self.memo, key)
        if cached is None and self.computed >= self.compute_limit:
            return self.unresolved_answer(node.node_id, node.expected_output_type)
        if self.memo is None:
            self.lookups += 1
        if cached is not None:
            if (not isinstance(cached, _public().TypedValue)
                    or cached.type_name != node.expected_output_type
                    or cached.semantic_release != self.release
                    or cached.state not in (
                        _public().ValueState.VALUE, _public().ValueState.NONE)
                    or cached.source_handle is not None):
                _public()._invalid("BAMF_DAG_MEMO_VALUE_INVALID")
            if self.artifact_owner is not None:
                sources, parents, policy_digest, rights_digest = (
                    self.cache_dependencies(refs, spec, numeric))
                self.artifact_owner.require_exact_cache(
                    key=key,
                    content_digest=_public().contract_digest(cached),
                    source_handles=sources,
                    predecessor_keys=parents,
                    operator_id=spec.operator_id,
                    semantic_release=self.release,
                    policy_digest=policy_digest,
                    rights_digest=rights_digest,
                    task_sha256=self.support_task_sha256)
            self.hits += 1
            value = cached
        else:
            self.computed += 1
            value = _public()._compute_after_authorization(spec, inputs, self.binding)
            if self.memo is not None and value.state in (
                    _public().ValueState.VALUE, _public().ValueState.NONE):
                _public()._memo_put_verified(self.memo, key, value)
                if self.artifact_owner is not None:
                    sources, parents, policy_digest, rights_digest = (
                        self.cache_dependencies(refs, spec, numeric))
                    self.artifact_owner.materialize_exact_cache(
                        key=key,
                        content_digest=_public().contract_digest(value),
                        source_handles=sources,
                        predecessor_keys=parents,
                        operator_id=spec.operator_id,
                        semantic_release=self.release,
                        policy_digest=policy_digest,
                        rights_digest=rights_digest,
                        task_sha256=self.support_task_sha256)
        self.results[node.node_id] = value
        self.lineage[node.node_id] = key
        self.executed.append(node.node_id)
        if value.state is not _public().ValueState.VALUE and (
                node.node_id != self.program.output_node_id):
            return self.unresolved_answer(node.node_id, node.expected_output_type)
        return _CONTINUE
