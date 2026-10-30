"""Detached semantic-bank staging and tied readout for A02."""
from __future__ import annotations

from typing import Mapping

from ...runtime.model_topology_v2 import (
    GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
    initialize_bamf_row,
)
from ..atlas_projection import BANK_SIZE
from .vocabulary_contracts import (
    ADAMW_ARRAYS_PER_ROW, FP32_BYTES, STAGED_ONLY,
    CandidateState, VocabularyAllocation, VocabularyBankParent,
    VocabularyExtension, VocabularyPrior, _invalid,
)
from .vocabulary_factors import prepare_identity_factors
from .vocabulary_planning import _plan_from_snapshot, _verified_prior

def _mask(indices: tuple[int, ...], capacity: int) -> bytes:
    mask = bytearray((capacity + 7) // 8)
    for index in indices:
        if not 0 <= index < capacity:
            _invalid("BAMF_VOCABULARY_MASK_INDEX_INVALID")
        mask[index // 8] |= 1 << (index % 8)
    return bytes(mask)


def _validate_bank_parent(parent: VocabularyBankParent) -> None:
    import mlx.core as mx

    if (type(parent) is not VocabularyBankParent
            or type(parent.prior) is not VocabularyPrior
            or type(parent.run_seed) is not int or parent.run_seed < 0
            or type(parent.resource_budget_bytes) is not int
            or parent.resource_budget_bytes < 0
            or not isinstance(parent.feature_parameters, Mapping)
            or any(not isinstance(part, tuple) for part in (
                parent.weights, parent.moments_m, parent.moments_v))
            or not isinstance(parent.row_counts, tuple)):
        _invalid("BAMF_VOCABULARY_BANK_PARENT_INVALID")
    count = parent.prior.extents.semantic_bank_count
    if any(len(part) != count for part in (
            parent.weights, parent.moments_m, parent.moments_v)):
        _invalid("BAMF_VOCABULARY_BANK_COUNT_INVALID")
    shape = (BANK_SIZE, ModelTopologySpecV2.width)
    for bank in range(count):
        for part in (parent.weights, parent.moments_m, parent.moments_v):
            value = part[bank]
            if (not isinstance(value, mx.array)
                    or value.dtype != mx.float32 or value.shape != shape):
                _invalid("BAMF_VOCABULARY_BANK_SHAPE_INVALID")
    if (any(not isinstance(item, tuple) or len(item) != 2
            or type(item[0]) is not int or type(item[1]) is not int
            or item[1] < 0 for item in parent.row_counts)
            or tuple(index for index, _ in parent.row_counts)
            != tuple(sorted(set(index for index, _ in parent.row_counts)))):
        _invalid("BAMF_VOCABULARY_ROW_COUNTS_INVALID")


def _verified_extension(parent, plan):
    _validate_bank_parent(parent)
    if (type(plan) is not VocabularyExtension
            or not isinstance(plan.allocations, tuple)
            or any(type(item) is not VocabularyAllocation
                   for item in plan.allocations)):
        _invalid("BAMF_VOCABULARY_PLAN_INVALID")
    snapshot = _verified_prior(parent.prior)
    expected = _plan_from_snapshot(
        parent.prior,
        tuple(item.semantic_id for item in plan.allocations),
        ModelTopologySpecV2(), snapshot,
    )
    if plan != expected:
        _invalid("BAMF_VOCABULARY_PLAN_SOURCE_REPLAY_MISMATCH")
    old_active = tuple(
        snapshot.abi_for_semantic(name).index
        for name in parent.prior.active_semantic_ids)
    if tuple(index for index, _ in parent.row_counts) != old_active:
        _invalid("BAMF_VOCABULARY_ROW_COUNTS_ACTIVE_SET_MISMATCH")
    old_count = parent.prior.extents.semantic_bank_count
    estimated_bytes = (
        (plan.bank_count - old_count) * BANK_SIZE * ModelTopologySpecV2.width
        * FP32_BYTES * ADAMW_ARRAYS_PER_ROW
    )
    if estimated_bytes > parent.resource_budget_bytes:
        _invalid("BAMF_VOCABULARY_BANK_RESOURCE_BUDGET_EXCEEDED")
    source_plan, factors = prepare_identity_factors(
        snapshot, parent.prior.features,
        tuple(item.semantic_id for item in plan.allocations),
        parent.feature_parameters,
        extents=parent.prior.extents,
    )
    if (source_plan.digest != plan.prospective_feature_digest
            or tuple(name for name, _ in factors)
            != tuple(item.semantic_id for item in plan.allocations)):
        _invalid("BAMF_VOCABULARY_FACTOR_SOURCE_MISMATCH")
    if source_plan.type_map != parent.prior.features.type_map:
        _invalid("BAMF_VOCABULARY_FACTOR_TABLE_EXTENSION_REQUIRED")
    return snapshot, old_count, estimated_bytes, factors


def _detached_bank_copies(parent, plan, old_count):
    import numpy as np

    touched = {item.bank for item in plan.allocations}
    weights, moments_m, moments_v = [], [], []
    shape = (BANK_SIZE, ModelTopologySpecV2.width)
    for bank in range(plan.bank_count):
        if bank < old_count and bank not in touched:
            weights.append(parent.weights[bank])
            moments_m.append(parent.moments_m[bank])
            moments_v.append(parent.moments_v[bank])
        elif bank < old_count:
            weights.append(np.asarray(parent.weights[bank]).copy())
            moments_m.append(np.asarray(parent.moments_m[bank]).copy())
            moments_v.append(np.asarray(parent.moments_v[bank]).copy())
        else:
            weights.append(np.zeros(shape, dtype=np.float32))
            moments_m.append(np.zeros(shape, dtype=np.float32))
            moments_v.append(np.zeros(shape, dtype=np.float32))
    return touched, weights, moments_m, moments_v


def _stage_extension_rows(parent, plan, factors, touched, weights, moments_m, moments_v):
    import mlx.core as mx

    staged_extents = GenerationExtents(
        plan.bank_count, parent.prior.extents.motif_page_count,
        plan.active_semantic_digest,
        parent.prior.extents.motif_key_map_digest,
        parent.prior.extents.factor_map_digest,
    )
    identity_specs = {
        item.name: item for item in expected_bamf_shapes(
            ModelTopologySpecV2(), staged_extents)
        if item.name.startswith("identity.bank.")
    }
    for item, (_, factor) in zip(plan.allocations, factors):
        parameter = identity_specs[f"identity.bank.{item.bank}"]
        weights[item.bank][item.row] = initialize_bamf_row(
            parameter, run_seed=parent.run_seed,
            row_id=item.semantic_id, factor=factor)
        moments_m[item.bank][item.row] = 0
        moments_v[item.bank][item.row] = 0
    staged_weights = tuple(
        mx.array(value, dtype=mx.float32) if bank in touched else value
        for bank, value in enumerate(weights))
    staged_m = tuple(
        mx.array(value, dtype=mx.float32) if bank in touched else value
        for bank, value in enumerate(moments_m))
    staged_v = tuple(
        mx.array(value, dtype=mx.float32) if bank in touched else value
        for bank, value in enumerate(moments_v))
    mx.eval(staged_weights, staged_m, staged_v)
    return staged_extents, staged_weights, staged_m, staged_v


def _candidate_state(parent, plan, snapshot, estimated_bytes, staged):
    staged_extents, staged_weights, staged_m, staged_v = staged
    by_index = {entry.index: entry.semantic_id for entry in snapshot.abi_entries}
    counts = tuple(sorted(
        (*parent.row_counts, *((item.abi_index, 0) for item in plan.allocations))))
    return CandidateState(
        parent_generation_id=parent.prior.generation_id,
        source_allocation_digest=plan.source_allocation_digest,
        extents=staged_extents,
        weights=staged_weights, moments_m=staged_m, moments_v=staged_v,
        row_counts=counts,
        active_indices=plan.active_indices,
        active_mask=_mask(plan.active_indices, plan.bank_count * BANK_SIZE),
        output_domain=tuple(
            (index, by_index[index]) for index in plan.active_indices),
        registry_mirror_delta=plan.allocations,
        estimated_new_bank_bytes=estimated_bytes,
    )


def apply_vocabulary_extension(
    parent: VocabularyBankParent,
    plan: VocabularyExtension,
) -> CandidateState:
    """Build a detached bank candidate without adopting a source or student."""
    snapshot, old_count, estimated_bytes, factors = _verified_extension(parent, plan)
    touched, weights, moments_m, moments_v = _detached_bank_copies(
        parent, plan, old_count)
    staged = _stage_extension_rows(
        parent, plan, factors, touched, weights, moments_m, moments_v)
    return _candidate_state(parent, plan, snapshot, estimated_bytes, staged)

def staged_tied_logits(
    candidate: CandidateState,
    hidden: object,
) -> tuple[tuple[int, ...], object]:
    """Only active ABI rows compete, in global index order without modulo alias."""
    import mlx.core as mx

    if (type(candidate) is not CandidateState
            or candidate.status != STAGED_ONLY
            or not isinstance(hidden, mx.array)
            or hidden.dtype != mx.float32
            or hidden.shape != (ModelTopologySpecV2.width,)
            or len(candidate.weights) != candidate.extents.semantic_bank_count
            or tuple(index for index, _ in candidate.output_domain)
            != candidate.active_indices
            or candidate.active_mask != _mask(
                candidate.active_indices,
                candidate.extents.semantic_bank_count * BANK_SIZE)):
        _invalid("BAMF_VOCABULARY_READOUT_INVALID")
    logits = []
    for bank, weights in enumerate(candidate.weights):
        rows = tuple(
            index % BANK_SIZE for index in candidate.active_indices
            if index // BANK_SIZE == bank)
        if rows:
            logits.append(mx.take(
                weights, mx.array(rows, dtype=mx.int32), axis=0) @ hidden)
    if not logits:
        _invalid("BAMF_VOCABULARY_READOUT_EMPTY")
    output = mx.concatenate(logits)
    mx.eval(output)
    return candidate.active_indices, output
