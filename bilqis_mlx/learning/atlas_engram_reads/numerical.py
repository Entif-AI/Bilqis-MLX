"""Experimental gated motif arithmetic; no source-admission authority."""
from __future__ import annotations

import math

import mlx.core as mx

from bilqis_mlx.semantics.context_eligibility import ApprovedContextProjection, ContextHold, ContextPolicy, SourceFrontier, TaskScope, project_context
from bilqis_mlx.semantics.frame_schema import AtomicFrame
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from ..atlas_engram import (
    INITIAL_MOTIF_CAPACITY, MotifFrameInput, MotifManifest, motif_keys,
)
from ..atlas_engram_parameters import MotifParameterView, SITE_COUNT


from .records import _invalid, WIDTH, MOTIF_WIDTH, READ_TENSOR_RANK, FEATURE_AXIS, BATCH_PREFIX_AXES, MotifReadPosition, MotifReadResult
from .source import _schema_grant_live

def _validate_candidate_inputs(
    site_index, hidden, features, positions, tasks, frontiers, policies,
    manifest, parameters,
):
    if (type(site_index) is not int or not 0 <= site_index < SITE_COUNT
            or type(manifest) is not MotifManifest
            or type(parameters) is not MotifParameterView
            or parameters.site_index != site_index
            or manifest.capacity > parameters.page_count * INITIAL_MOTIF_CAPACITY
            or not isinstance(hidden, mx.array) or hidden.ndim != READ_TENSOR_RANK
            or hidden.shape[FEATURE_AXIS] != WIDTH or hidden.dtype != mx.float32
            or not isinstance(features, mx.array)
            or features.shape != (*hidden.shape[:BATCH_PREFIX_AXES], MOTIF_WIDTH)
            or features.dtype != mx.float32
            or not isinstance(positions, tuple)
            or not isinstance(tasks, tuple)
            or not isinstance(frontiers, tuple)
            or not isinstance(policies, tuple)
            or not (len(positions) == len(tasks) == len(frontiers)
                    == len(policies) == hidden.shape[0])
            or any(not isinstance(row, tuple) or len(row) != hidden.shape[1]
                   or any(item is not None and type(item) is not MotifReadPosition
                          for item in row) for row in positions)
            or any(type(item) is not TaskScope for item in tasks)
            or any(type(item) is not SourceFrontier for item in frontiers)
            or any(type(item) is not ContextPolicy for item in policies)
            or not bool(mx.all(mx.isfinite(hidden)))
            or not bool(mx.all(mx.isfinite(features)))):
        _invalid()
    parameters.__post_init__()


def _read_motif_unqualified_candidate(
    *,
    site_index: int,
    hidden: mx.array,
    features: mx.array,
    positions: tuple[tuple[MotifReadPosition | None, ...], ...],
    tasks: tuple[TaskScope, ...],
    frontiers: tuple[SourceFrontier, ...],
    policies: tuple[ContextPolicy, ...],
    manifest: MotifManifest,
    parameters: MotifParameterView,
) -> MotifReadResult:
    """Experimental numerical proof only; not a source-authorized entrypoint.

    A row is source-gated as a *set* before a slot is gathered, so a
    disallowed join cannot leak through individually eligible frames.
    Caller-supplied feature128 must be bound to B02 source features by
    the B11 integration owner; it grants no source eligibility here.
    """
    _validate_candidate_inputs(
        site_index, hidden, features, positions, tasks, frontiers, policies,
        manifest, parameters)
    projections = {name: parameters[name] for name in (
        "projection", "norm", "gate_hidden", "gate_feature", "bias")}
    output_rows = []
    dispositions = []
    context_digests = []
    participating = set()
    any_hit = False
    for row_index, row in enumerate(positions):
        envelopes = tuple(item.envelope for item in row if item is not None)
        task, frontier, policy = tasks[row_index], frontiers[row_index], policies[row_index]
        if not envelopes:
            output_rows.append(tuple(hidden[row_index, index] for index in range(hidden.shape[1])))
            dispositions.append(("MISS",) * hidden.shape[1])
            context_digests.append(None)
            continue
        projection = project_context(envelopes, task, frontier, policy)
        if isinstance(projection, ContextHold):
            output_rows.append(tuple(hidden[row_index, index] for index in range(hidden.shape[1])))
            dispositions.append(tuple(
                "HELD" if item is not None else "MISS" for item in row))
            context_digests.append(None)
            continue
        if type(projection) is not ApprovedContextProjection:
            _invalid()
        context_digests.append(projection.digest)
        output = []
        status = []
        for index, item in enumerate(row):
            state = hidden[row_index, index]
            if item is None or type(item.envelope.frame) is AtomicFrame:
                output.append(state)
                status.append("MISS")
                continue
            if task.semantic_release != manifest.semantic_release:
                output.append(state)
                status.append("FOREIGN_RELEASE")
                continue
            if (projection.frame(item.envelope.frame_handle)
                    != item.envelope.frame):
                _invalid()
            if not _schema_grant_live(
                    item.schema, item.envelope, task, frontier):
                output.append(state)
                status.append("HELD")
                continue
            exact, structural = motif_keys(
                MotifFrameInput(item.envelope.frame, item.schema),
                manifest.semantic_release)
            slot_id = manifest.lookup(exact)
            disposition = "EXACT"
            if slot_id is None:
                slot_id = manifest.lookup(structural)
                disposition = "STRUCTURAL"
            if slot_id is None:
                output.append(state)
                status.append("MISS")
                continue
            page_index, local_index = divmod(slot_id, INITIAL_MOTIF_CAPACITY)
            slot_vector = parameters[f"page.{page_index}"][local_index]
            normalized = mx.fast.rms_norm(
                state, projections["norm"], ModelTopologySpecV2.rms_norm_epsilon)
            gate_logit = (
                mx.sum(projections["gate_hidden"] * normalized) / math.sqrt(WIDTH)
                + mx.sum(projections["gate_feature"] * features[row_index, index])
                / math.sqrt(MOTIF_WIDTH)
                + projections["bias"][0]
            )
            gate = mx.sigmoid(gate_logit)
            output.append(state + gate * (projections["projection"] @ slot_vector))
            status.append(disposition)
            participating.add(slot_id)
            any_hit = True
        output_rows.append(tuple(output))
        dispositions.append(tuple(status))
    if not any_hit:
        return MotifReadResult(
            hidden, tuple(dispositions), (), tuple(context_digests))
    return MotifReadResult(
        mx.stack(tuple(mx.stack(row) for row in output_rows)),
        tuple(dispositions), tuple(sorted(participating)),
        tuple(context_digests),
    )
