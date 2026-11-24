"""Private numerical AdamW counts; full-model candidate custody remains separate.

No durable student, participation policy, clipping policy, generation publication
or historical optimizer migration is implemented by this numerical seam.
"""
from __future__ import annotations

from typing import Mapping

import mlx.core as mx
import numpy as np

from bilqis_mlx.runtime.optimizer_count_geometry import declared_update_count_shape
from bilqis_mlx.runtime.optimizer_step import (
    adamw_leaf_update, adamw_selected_rows_update, optimizer_parent_witness_matches,
)

from .atlas_optimizer_contracts import (
    ADAM_MOMENT_COUNT, DENSE_COUNT_RANK, ROW_COUNT_RANK, ROW_SELECTION_PARTS,
    STATE_SCHEMA, UINT64_MAX, AdamWHyperparameters, AdamWStateTree,
    _finite_number, _invalid, _issue_learning_first_state,
    reconcile_b01_optimizer_manifest,
)
from .atlas_optimizer_preflight import (
    _learning_first_preflight, _masked_clipped_gradients,
    _masked_clipped_gradients_unchecked, _preflight,
)

AdamWHyperparameters.__module__ = __name__
AdamWStateTree.__module__ = __name__


def _validated_max_norm(max_norm):
    if max_norm is not None and (not _finite_number(max_norm) or max_norm <= 0):
        _invalid()


def _standard_update_admission(
        parent, gradients, participation, hyperparameters, decay, loss_bearing,
        max_norm, participation_authority):
    valid, any_participation = _preflight(
        parent, gradients, participation, hyperparameters, decay, loss_bearing,
        participation_authority)
    if not loss_bearing:
        mx.eval(valid, any_participation)
        if not bool(valid):
            _invalid()
        return None, any_participation
    finite_norm = None
    if max_norm is not None:
        gradients, norm = _masked_clipped_gradients_unchecked(
            parent, gradients, participation, max_norm=max_norm)
        finite_norm = mx.isfinite(norm)
    mx.eval(valid, any_participation, *(() if finite_norm is None else (finite_norm,)))
    if not bool(valid) or (finite_norm is not None and not bool(finite_norm)):
        _invalid()
    return gradients, any_participation


def _learning_first_update_admission(
        parent, gradients, participation, hyperparameters, decay, loss_bearing,
        max_norm, participation_authority):
    count_checks, any_participation = _learning_first_preflight(
        parent, gradients, participation, hyperparameters, decay, loss_bearing,
        participation_authority)
    if not loss_bearing:
        if count_checks:
            count_valid = mx.all(mx.stack(tuple(count_checks)))
            mx.eval(count_valid)
            if not bool(count_valid):
                _invalid()
        return None, any_participation
    finite_norm = None
    if max_norm is not None:
        gradients, norm = _masked_clipped_gradients_unchecked(
            parent, gradients, participation, max_norm=max_norm)
        finite_norm = mx.isfinite(norm)
    runtime_checks = tuple(count_checks) + (() if finite_norm is None else (finite_norm,))
    if runtime_checks:
        runtime_valid = mx.all(mx.stack(runtime_checks))
        mx.eval(runtime_valid)
        if not bool(runtime_valid):
            _invalid()
    return gradients, any_participation


def _apply_adamw_updates(
        parent, gradients, participation, hyperparameters, decay,
        participation_authority):
    parameters, first, second, counts = (dict(tree) for tree in
                                         (parent.parameters, parent.m, parent.v,
                                          parent.update_counts))
    for name, parameter in parent.parameters.items():
        mask = participation[name]
        count = parent.update_counts[name]
        authority = None if participation_authority is None else participation_authority[name]
        if authority is not None and not authority[0] and not authority[1]:
            continue
        kwargs = dict(
            learning_rate=hyperparameters.learning_rate,
            betas=hyperparameters.betas,
            eps=hyperparameters.eps,
            weight_decay=hyperparameters.weight_decay if decay[name] else 0.,
        )
        if authority is not None and authority[1]:
            updated, next_first, next_second, next_count = adamw_selected_rows_update(
                parameter, parent.m[name], parent.v[name], count, gradients[name],
                mask, authority[1], **kwargs)
        else:
            updated, next_first, next_second, next_count = adamw_leaf_update(
                parameter, parent.m[name], parent.v[name], count,
                gradients[name], mask, **kwargs)
        parameters[name] = updated
        first[name] = next_first
        second[name] = next_second
        counts[name] = next_count
    return parameters, first, second, counts


def _adamw_update(parent: AdamWStateTree, gradients: Mapping[str, mx.array],
                  participation: Mapping[str, mx.array], hyperparameters: AdamWHyperparameters, *,
                  decay: Mapping[str, bool], loss_bearing: bool = True,
                  max_norm: float | None = None, parent_witness=None,
                  participation_authority=None, learning_first: bool = False) -> AdamWStateTree:
    """Apply native AdamW only to selected numerical leaves/rows, without publication.

    max_norm uses the existing global clip after participation masking. When
    omitted, supplied gradients must already follow the clipping contract.
    Masks are explicit Boolean scalars or row vectors, never inferred from
    nonzero gradients. Selected zero gradients still advance moments/counts.
    No-loss and wholly frozen steps return the original state object.
    """
    # Numerical validation belongs to this exact consumption boundary.  A
    # witness may attest object ownership, but MLX leaves remain mutable, so it
    # must never substitute for validating the state at the instant it is used.
    if parent_witness is not None and not optimizer_parent_witness_matches(parent_witness, parent):
        _invalid()
    _validated_max_norm(max_norm)
    if learning_first:
        admitted, any_participation = _learning_first_update_admission(
            parent, gradients, participation, hyperparameters, decay, loss_bearing,
            max_norm, participation_authority)
    else:
        admitted, any_participation = _standard_update_admission(
            parent, gradients, participation, hyperparameters, decay, loss_bearing,
            max_norm, participation_authority)
    if admitted is None:
        return parent
    gradients = admitted
    if not any_participation if learning_first else not bool(any_participation):
        return parent
    parameters, first, second, counts = _apply_adamw_updates(
        parent, gradients, participation, hyperparameters, decay,
        participation_authority)
    if learning_first:
        return _issue_learning_first_state(parameters, first, second, counts)
    return AdamWStateTree(parameters, first, second, counts)


def _create_unbound_bamf_optimizer(spec, extents, *, run_seed):
    """Reuse the complete topology owner's disposable initialization verbatim.

    This fresh UNBOUND state has no admitted source rows or production caller.
    It is not a historical optimizer migration or a checkpoint-generation grant.
    Count geometry follows declared table initializers; vector seeds and dense
    matrices retain scalar counts. Decay flags come only from the same ledger.
    """
    from bilqis_mlx.runtime.model_topology_v2 import (
        create_unbound_bamf_state, expected_bamf_shapes,
    )

    parameters, native, manifest = create_unbound_bamf_state(spec, extents, run_seed=run_seed)
    declared = expected_bamf_shapes(spec, extents)
    counts = {
        item.name: mx.zeros(declared_update_count_shape(item), dtype=mx.uint64)
        for item in declared
    }
    state = AdamWStateTree(parameters, {item.name: native[item.name]["m"] for item in declared},
                           {item.name: native[item.name]["v"] for item in declared}, counts)
    decay = reconcile_b01_optimizer_manifest(state, spec, extents)
    return state, decay, manifest
