"""Loss and gradient ownership layered on the exact live B11 forward."""
from __future__ import annotations

import mlx.core as mx

from bilqis_mlx.learning.atlas_readout import (
    AnswerPlan, DecisionKind, DecisionOutput, ExecutionMode, answer_loss,
)
from bilqis_mlx.semantics.frame_schema import ConceptRef
from bilqis_mlx.runtime.model_topology_v2 import (
    ModelTopologySpecV2, validate_bamf_parameters,
)

from .atlas_model_backend import Backend, model_backend
from .atlas_model_contracts import (
    BamfCompiledBatch, BamfGradientExecution, BamfLossExecution,
    _FORWARD_ISSUANCE, _LOSS_EXECUTION_ISSUER, _invalid,
    _issue_loss_execution,
)
from .atlas_model_forward import _forward_bamf_impl


def _loss_participation(output, targets, mask, record):
    """Return exact semantic/role rows read by the supervised loss ancestry."""
    labelled = {target.decision_id for target in targets}
    specs = {item.decision_id: item for item in output.plan.decisions}
    supervised = {
        item.decision_id for item in output.decisions
        if mask.get(item.decision_id, False) and item.decision_id in labelled
    }
    relevant = set(supervised)
    pending = list(supervised)
    while pending:
        current = pending.pop()
        for parent in specs[current].depends_on:
            if parent not in relevant:
                relevant.add(parent)
                pending.append(parent)

    semantic = set()
    role_denominator = set()
    for item in output.decisions:
        if item.decision_id not in supervised:
            continue
        if item.kind is DecisionKind.VALUE and type(item.candidates[0]) is ConceptRef:
            semantic.update(
                divmod(value.abi_index, ModelTopologySpecV2.semantic_bank_rows)
                for value in item.candidates
            )
        elif item.kind is DecisionKind.ROLE:
            role_denominator.update(value.role_id for value in item.candidates)

    feedback = {
        divmod(item.value.abi_index, ModelTopologySpecV2.semantic_bank_rows)
        for item in output.committed
        if item.decision_id in relevant - supervised and type(item.value) is ConceptRef
    }
    roles = dict(record.role_map)
    role_reads = {
        ("role", roles[specs[key].role_id or "NONE"])
        for key in relevant
    }
    semantic_features = {("role", roles[role]) for role in role_denominator}
    return (
        tuple(sorted(feedback)),
        tuple(sorted(semantic)),
        tuple(sorted(semantic_features)),
        tuple(sorted(role_reads)),
    )


def loss_bearing_bamf(
    output,
    targets: tuple[DecisionOutput, ...],
    mask,
) -> BamfLossExecution:
    """Bind a nonempty B10 supervised loss to the exact live B11 forward."""
    record = _FORWARD_ISSUANCE.require(output)
    if (
        type(targets) is not tuple
        or not targets
        or not isinstance(mask, dict)
        or not any(mask.values())
    ):
        _invalid("B11_LOSS_TARGET_REQUIRED")
    loss = answer_loss(output, targets, mask)
    if not bool(mx.all(mx.isfinite(loss.total))):
        _invalid("B11_LOSS_NONFINITE")
    return _issue_loss_execution(
        output, loss, record, _loss_participation(output, targets, mask, record))


def _bamf_value_and_grad_impl(
    backend: Backend,
    params,
    compiled_batch: BamfCompiledBatch,
    answer_plan: AnswerPlan,
    targets: tuple[DecisionOutput, ...],
    mask,
    cache=None,
) -> BamfGradientExecution:
    """Run one exact forward/loss/gradient dispatch with one execution identity."""
    holder = {}

    def objective(current):
        output = _forward_bamf_impl(
            backend,
            current,
            compiled_batch,
            answer_plan,
            ExecutionMode.INFERENCE,
            cache,
        )
        execution = loss_bearing_bamf(output, targets, mask)
        holder["execution"] = execution
        return execution.loss.total

    loss_total, gradients = mx.value_and_grad(objective)(params)
    mx.eval(loss_total, gradients)
    execution = holder.get("execution")
    if type(execution) is not BamfLossExecution:
        _invalid("B11_GRADIENT_EXECUTION_MISSING")
    validate_bamf_parameters(
        backend.topology, compiled_batch.compiled.extents, gradients)
    result = object.__new__(BamfGradientExecution)
    for name, value in (
        ("execution", execution),
        ("gradients", gradients),
        ("loss_total", loss_total),
        ("schema_version", "bilqis.mlx.b11-gradient-execution/v1"),
        ("_issuance", _LOSS_EXECUTION_ISSUER),
    ):
        object.__setattr__(result, name, value)
    result.__post_init__()
    return result


def bamf_value_and_grad(
    params,
    compiled_batch: BamfCompiledBatch,
    answer_plan: AnswerPlan,
    targets: tuple[DecisionOutput, ...],
    mask,
    cache=None,
) -> BamfGradientExecution:
    """Public gradient entrypoint through the same backend as direct inference."""
    return model_backend(ModelTopologySpecV2()).value_and_grad(
        params, compiled_batch, answer_plan, targets, mask, cache)


__all__ = ("loss_bearing_bamf", "bamf_value_and_grad")
