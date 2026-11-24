"""B11 vector-route evidence reconstruction."""
from __future__ import annotations

import mlx.core as mx
import numpy as np

from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.learning.atlas_readout import DecisionKind
from bilqis_mlx.semantics.frame_schema import ConceptRef

from ..atlas_model_contracts import (
    _FORWARD_ISSUANCE, _invalid, _issue_learning_participation_execution,
)
from .forward_preflight import (
    validate_decode_row_custody, validate_decode_row_input, validate_task_plan_custody,
)


_ROUTE_TRAJECTORY_NDIM = 2


def _route_output_from_materialized_logits(plan, row_index, trajectory_indices, route_logits):
    from bilqis_mlx.learning.atlas_readout.decisions import (
        DecodeStatus, DecisionOutput, commit_decisions, ready_decisions, start_decoding,
    )
    from bilqis_mlx.learning.atlas_readout.decoder.prediction import (
        DecisionLogits, ExecutionMode, ModelOutput, _issue_output,
    )

    ordered = tuple(
        {item.decision_id: item for item in plan.decisions}[key]
        for key in plan.execution_order)
    if (trajectory_indices.ndim != _ROUTE_TRAJECTORY_NDIM
            or trajectory_indices.shape[0] != len(route_logits)
            or trajectory_indices.shape[0] < len(ordered)
            or row_index >= trajectory_indices.shape[1]):
        _invalid("B11_MICROBATCH_ROUTE_EVIDENCE_MISSING")
    evidence = {}
    for step, decision in enumerate(ordered):
        selected = int(trajectory_indices[step, row_index])
        if not 0 <= selected < len(decision.legal_values):
            _invalid("B11_MICROBATCH_TRAJECTORY_DRIFT")
        logits = route_logits[step][row_index, :len(decision.legal_values)]
        evidence[decision.decision_id] = (
            DecisionLogits(
                decision.decision_id, decision.kind, decision.legal_values, logits),
            DecisionOutput(decision.decision_id, decision.legal_values[selected]),
        )
    state = start_decoding(plan)
    records = []
    while state.status is DecodeStatus.ACTIVE:
        ready = ready_decisions(state)
        if not ready or any(item.decision_id not in evidence for item in ready):
            _invalid("B11_MICROBATCH_TRAJECTORY_DRIFT")
        outputs = tuple(evidence[item.decision_id][1] for item in ready)
        records.extend(evidence[item.decision_id][0] for item in ready)
        state = commit_decisions(state, outputs)
    if state.status is not DecodeStatus.COMPLETE:
        _invalid("B11_MICROBATCH_TRAJECTORY_DRIFT")
    return _issue_output(ModelOutput(
        plan, tuple(records), state.committed, state.status,
        ExecutionMode.INFERENCE, None, False),
        fingerprint=False, freeze_meaning=False)


def _refinement_participation(selection):
    if selection is None or not selection[1]:
        return (), False
    request, choices = selection
    roles = request.requested_roles
    if len(roles) > 1:
        _invalid("B11_REFINEMENT_MULTI_ROLE_UNRESOLVED")
    return ((roles[0] if roles else "NONE",),
            any(choice.passes > 0 for choice in choices))


def _compact_loss_participation(plan, targets, mask, selected, record):
    """Derive optimizer ancestry from plan + selected route, without logits/output."""
    specs = {item.decision_id: item for item in plan.decisions}
    labelled = {target.decision_id for target in targets}
    supervised = {
        decision_id for decision_id, enabled in mask.items()
        if enabled and decision_id in labelled
    }
    if not supervised or not supervised <= set(selected):
        _invalid("B11_LOSS_TARGET_NOT_EXECUTED")
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
    for decision_id in supervised:
        item = specs[decision_id]
        if item.kind is DecisionKind.VALUE and type(item.legal_values[0]) is ConceptRef:
            semantic.update(
                divmod(value.abi_index, ModelTopologySpecV2.semantic_bank_rows)
                for value in item.legal_values
            )
        elif item.kind is DecisionKind.ROLE:
            role_denominator.update(value.role_id for value in item.legal_values)
    feedback = {
        divmod(selected[key].abi_index, ModelTopologySpecV2.semantic_bank_rows)
        for key in relevant - supervised
        if key in selected and type(selected[key]) is ConceptRef
    }
    roles = dict(record.role_map)
    role_reads = {
        ("role", roles[specs[key].role_id or "NONE"])
        for key in relevant
    }
    semantic_features = {("role", roles[role]) for role in role_denominator}
    return (
        tuple(sorted(feedback)), tuple(sorted(semantic)),
        tuple(sorted(semantic_features)), tuple(sorted(role_reads)),
    )


def microbatch_participation_from_route(
        backend, params, row_batches, answer_plans, targets, masks, producer,
        accepted_cache, execution_binding, refinement_selections, trajectory_indices):
    """Ordinary postflight ancestry without materializing hidden states or logits."""
    from bilqis_mlx.runtime.backbone_identity import require_execution_generation_binding
    from ..atlas_model_participation import _forward_participation

    generation = require_execution_generation_binding(
        execution_binding, params, spec=backend.topology,
        extents=row_batches[0].compiled.extents).generation_digest
    if (not isinstance(trajectory_indices, mx.array)
            or trajectory_indices.ndim != _ROUTE_TRAJECTORY_NDIM):
        _invalid("B11_MICROBATCH_ROUTE_EVIDENCE_MISSING")
    trajectory_indices = np.asarray(trajectory_indices, dtype=np.int64)
    executions = []
    for index, (row_batch, plan, row_targets, mask, refinement) in enumerate(zip(
            row_batches, answer_plans, targets, masks, refinement_selections)):
        ordered = tuple(
            {item.decision_id: item for item in plan.decisions}[key]
            for key in plan.execution_order)
        if (trajectory_indices.shape[0] < len(ordered)
                or index >= trajectory_indices.shape[1]):
            _invalid("B11_MICROBATCH_ROUTE_EVIDENCE_MISSING")
        selected = {}
        for step, decision in enumerate(ordered):
            choice = int(trajectory_indices[step, index])
            if not 0 <= choice < len(decision.legal_values):
                _invalid("B11_MICROBATCH_TRAJECTORY_DRIFT")
            selected[decision.decision_id] = decision.legal_values[choice]
        roles, refined = _refinement_participation(refinement)
        record = _forward_participation(
            params, row_batch, plan, None, producer, accepted_cache,
            roles, refined, producer_row_index=index,
            executed_decision_ids=tuple(plan.execution_order))
        if record.generation_binding != generation:
            _invalid("B11_TRAINING_AUTHORITY_GENERATION_MISMATCH")
        executions.append(_issue_learning_participation_execution(
            record, _compact_loss_participation(
                plan, row_targets, mask, selected, record)))
    return tuple(executions)


def microbatch_trace_from_route(
    backend, params, row_batches, answer_plans, targets, masks, producer, hidden,
    accepted_cache, execution_binding, salience_supervision, refinement_selections,
    trajectory_indices, route_logits, refinement_route_logits=(),
):
    from dataclasses import replace
    from bilqis_mlx.runtime.autodiff_trace import defer_host_tensor_validation
    from bilqis_mlx.runtime.backbone_identity import require_execution_generation_binding
    from ..atlas_model_participation import _forward_participation
    from ..atlas_model_training import learning_participation_bamf, loss_bearing_bamf

    if (hidden.shape[0] != len(row_batches)
            or len(refinement_selections) != len(row_batches)):
        _invalid("B11_MICROBATCH_HIDDEN_BATCH_MISMATCH")
    generation = require_execution_generation_binding(
        execution_binding, params, spec=backend.topology,
        extents=row_batches[0].compiled.extents).generation_digest
    if (not isinstance(trajectory_indices, mx.array)
            or trajectory_indices.ndim != _ROUTE_TRAJECTORY_NDIM):
        _invalid("B11_MICROBATCH_ROUTE_EVIDENCE_MISSING")
    trajectory_indices = np.asarray(trajectory_indices, dtype=np.int64)
    executions = []
    for index, (row_batch, plan, row_targets, mask, refinement) in enumerate(zip(
            row_batches, answer_plans, targets, masks, refinement_selections)):
        validate_decode_row_input(backend, row_batch, plan, hidden, index)
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import (
            strict_evidence_enabled,
        )
        if strict_evidence_enabled():
            validate_decode_row_custody(row_batch, plan, producer, index, generation)
            validate_task_plan_custody(row_batch, plan)
        if (row_batch.training_authority is not None
                and row_batch.training_authority.generation_binding != generation):
            _invalid("B11_TRAINING_AUTHORITY_GENERATION_MISMATCH")
        with defer_host_tensor_validation():
            output = _route_output_from_materialized_logits(
                plan, index, trajectory_indices, route_logits)
            roles, refined = _refinement_participation(refinement)
            row = row_batch.compiled.compiled.rows[0]
            route_supervision = tuple(
                (slot_logits[index], refinement[1][slot].passes)
                for slot, slot_logits in enumerate(refinement_route_logits)
                if refinement is not None and slot < len(refinement[1]))
            record = replace(
                _forward_participation(
                    params, row_batch, plan, output, producer, accepted_cache,
                    roles, refined, refinement_routing=bool(route_supervision),
                    producer_row_index=index),
                salience_hidden=hidden[index, len(row.positions) - 1],
                salience_parameters=params, compiled_batch=row_batch,
                refinement_route_supervision=route_supervision)
            _FORWARD_ISSUANCE.issue(output, record)
            if not strict_evidence_enabled() and salience_supervision is None:
                executions.append(learning_participation_bamf(
                    output, row_targets, mask))
            else:
                executions.append(loss_bearing_bamf(
                    output, row_targets, mask, salience_supervision=salience_supervision,
                    validate_finite=False))
    return tuple(executions)


__all__ = ("microbatch_participation_from_route", "microbatch_trace_from_route")
