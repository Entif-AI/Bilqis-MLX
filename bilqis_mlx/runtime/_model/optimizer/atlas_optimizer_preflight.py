"""Validation and clipping helpers for the BAMF AdamW numerical owner."""
from __future__ import annotations

from typing import Mapping

import mlx.core as mx
import numpy as np

from bilqis_mlx.runtime.mlx_parity import clip_gradients

from .atlas_optimizer_contracts import (
    DENSE_COUNT_RANK, ROW_COUNT_RANK, ROW_SELECTION_PARTS, UINT64_MAX,
    AdamWHyperparameters, AdamWStateTree, _finite_number, _invalid,
    _state_numerical_checks,
)

def _validate_step_inputs(parent, gradients, participation):
    if (type(parent) is not AdamWStateTree or
            any(not isinstance(tree, Mapping) or set(tree) != set(parent.parameters)
                for tree in (gradients, participation))):
        _invalid()
    parent.validate_structure()
    checks = _state_numerical_checks(parent)
    for name, parameter in parent.parameters.items():
        gradient, mask = gradients[name], participation[name]
        if (not isinstance(gradient, mx.array) or gradient.shape != parameter.shape
                or gradient.dtype != mx.float32
                or not isinstance(mask, mx.array) or mask.dtype != mx.bool_ or
                mask.shape != parent.update_counts[name].shape):
            _invalid()
        checks.append(mx.all(mx.isfinite(gradient)))
    return checks


def _participation_authority_checks(parent, participation, authority):
    """Validate owner-issued row selections and bind them to device masks."""
    if authority is None:
        return []
    if not isinstance(authority, Mapping) or set(authority) != set(parent.parameters):
        _invalid()
    checks = []
    for name, count in parent.update_counts.items():
        selection = authority[name]
        if type(selection) is not tuple or len(selection) != ROW_SELECTION_PARTS:
            _invalid()
        whole, rows = selection
        if (type(whole) is not bool or type(rows) is not tuple
                or any(type(row) is not int or row < 0 for row in rows)
                or rows != tuple(sorted(set(rows)))
                or (whole and rows)):
            _invalid()
        mask = participation[name]
        if count.ndim == DENSE_COUNT_RANK:
            if rows:
                _invalid()
            expected = mx.array(whole, dtype=mx.bool_)
        else:
            if any(row >= count.shape[0] for row in rows):
                _invalid()
            expected = mx.ones_like(mask) if whole else mx.zeros_like(mask)
            if rows:
                expected[mx.array(rows, dtype=mx.uint32)] = True
        checks.append(mx.all(mask == expected))
    return checks


def _preflight(parent, gradients, participation, hyperparameters, decay, loss_bearing,
               participation_authority=None):
    checks = _validate_step_inputs(parent, gradients, participation)
    if (type(hyperparameters) is not AdamWHyperparameters or type(loss_bearing) is not bool or
            not isinstance(decay, Mapping) or set(decay) != set(parent.parameters) or
            any(type(value) is not bool for value in decay.values())):
        _invalid()
    hyperparameters.__post_init__()
    checks.extend(_participation_authority_checks(
        parent, participation, participation_authority))
    if loss_bearing:
        maximum = mx.array(np.array(UINT64_MAX, dtype=np.uint64))
        checks.extend(
            ~mx.any(participation[name] & (count == maximum))
            for name, count in parent.update_counts.items())
    any_participation = mx.any(mx.stack(tuple(
        mx.any(mask) for mask in participation.values())))
    valid = mx.all(mx.stack(tuple(checks)))
    return valid, any_participation


def _learning_first_preflight(
        parent, gradients, participation, hyperparameters, decay, loss_bearing,
        participation_authority):
    """Ordinary-training checks that are directly required to execute the update."""
    if (type(parent) is not AdamWStateTree
            or not isinstance(gradients, Mapping)
            or not gradients
            or not isinstance(participation, Mapping)
            or not set(gradients) <= set(parent.parameters)
            or set(participation) != set(parent.parameters)
            or type(hyperparameters) is not AdamWHyperparameters
            or type(loss_bearing) is not bool
            or not isinstance(decay, Mapping)
            or set(decay) != set(parent.parameters)
            or any(type(value) is not bool for value in decay.values())
            or not isinstance(participation_authority, Mapping)
            or set(participation_authority) != set(parent.parameters)):
        _invalid()
    parent.validate_structure()
    hyperparameters.__post_init__()
    selected_count_checks = []
    active_names = set()
    any_participation = False
    maximum = mx.array(np.array(UINT64_MAX, dtype=np.uint64))
    for name, parameter in parent.parameters.items():
        mask = participation[name]
        if (not isinstance(mask, mx.array) or mask.dtype != mx.bool_
                or mask.shape != parent.update_counts[name].shape):
            _invalid()
        selection = participation_authority[name]
        if type(selection) is not tuple or len(selection) != ROW_SELECTION_PARTS:
            _invalid()
        whole, rows = selection
        if (type(whole) is not bool or type(rows) is not tuple
                or any(type(row) is not int or row < 0 for row in rows)
                or rows != tuple(sorted(set(rows))) or (whole and rows)):
            _invalid()
        count = parent.update_counts[name]
        if count.ndim == DENSE_COUNT_RANK:
            if rows:
                _invalid()
            if whole and loss_bearing:
                selected_count_checks.append(count != maximum)
            if whole:
                active_names.add(name)
            any_participation = any_participation or whole
        else:
            if any(row >= count.shape[0] for row in rows):
                _invalid()
            if whole and loss_bearing:
                selected_count_checks.append(~mx.any(count == maximum))
            elif rows and loss_bearing:
                selected_count_checks.append(
                    ~mx.any(count[mx.array(rows, dtype=mx.uint32)] == maximum))
            if whole or rows:
                active_names.add(name)
            any_participation = any_participation or whole or bool(rows)
    if not active_names <= set(gradients):
        _invalid()
    for name, gradient in gradients.items():
        parameter = parent.parameters[name]
        if (not isinstance(gradient, mx.array) or gradient.shape != parameter.shape
                or gradient.dtype != mx.float32):
            _invalid()
    return selected_count_checks, any_participation


def _masked_clipped_gradients_unchecked(parent, gradients, participation, *, max_norm):
    """Mask supplied participation before the existing global FP32 norm clip.

    This numerical adapter does not attest that masks came from actual model
    execution. The full-model owner must supply that independent provenance.
    """
    if not _finite_number(max_norm) or max_norm <= 0:
        _invalid()
    masked = {}
    for name, gradient in gradients.items():
        mask = participation[name]
        if mask.ndim == ROW_COUNT_RANK:
            mask = mask.reshape((-1,) + (1,) * (gradient.ndim - 1))
        masked[name] = mx.where(mask, gradient, mx.zeros_like(gradient))
    clipped, norm = clip_gradients(mx, masked, max_norm=max_norm)
    return clipped, norm


def _masked_clipped_gradients(parent, gradients, participation, *, max_norm):
    """Standalone clipping boundary with its own numerical finiteness check."""
    clipped, norm = _masked_clipped_gradients_unchecked(
        parent, gradients, participation, max_norm=max_norm)
    finite_norm = mx.isfinite(norm)
    mx.eval(finite_norm)
    if not bool(finite_norm):
        _invalid()
    return clipped, norm
