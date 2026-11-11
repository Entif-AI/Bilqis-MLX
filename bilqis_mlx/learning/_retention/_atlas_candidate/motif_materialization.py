"""Source-qualified B07 motif allocation materialization for B12 candidates."""
from __future__ import annotations

import mlx.core as mx
import numpy as np

from bilqis_mlx.learning.atlas_engram import (
    INITIAL_MOTIF_CAPACITY, initialize_planned_motif_slot,
)
from bilqis_mlx.learning.atlas_engram_transaction import CandidateMotifSnapshot
from bilqis_mlx.runtime.atlas_optimizer import (
    AdamWStateTree, reconcile_b01_optimizer_manifest,
)
from bilqis_mlx.runtime.optimizer_count_geometry import declared_update_count_shape
from bilqis_mlx.runtime.topology_v2.initialization import initialize_bamf_parameter

from .common import invalid
def _array_copy(value):
    return np.array(value, copy=True)


def _require_zero_row(tree, name, row):
    if np.any(np.asarray(tree[name][row]) != 0):
        invalid()


def _stage_candidate_motif_allocation_impl(
        issue_transition, candidate, source_continuation, *,
        spec, parent_extents, candidate_extents, run_seed: int):
    """Terminally materialize one sealed B07 proposal into speculative B12 state."""
    from .transaction import CandidateTransaction, _issue_transaction
    from bilqis_mlx.runtime.bamf_bundle.source_continuation import (
        _require_source_qualified_continuation,
    )
    from bilqis_mlx.runtime.model_topology_v2 import (
        GenerationExtents, ModelTopologySpecV2, expected_bamf_shapes,
    )

    continuation = _require_source_qualified_continuation(source_continuation)
    approved = continuation.approved
    motif_candidate = approved.candidate
    if (type(candidate) is not CandidateTransaction
            or type(motif_candidate) is not CandidateMotifSnapshot
            or type(spec) is not ModelTopologySpecV2
            or type(parent_extents) is not GenerationExtents
            or type(candidate_extents) is not GenerationExtents
            or type(run_seed) is not int or run_seed < 0
            or candidate.motif_transition is not None
            or candidate.update_steps < 1
            or candidate.parent.custody is None
            or continuation.parent_manifest_sha256
            != candidate.parent.custody.manifest_sha256
            or continuation.parent_extents_sha256 != parent_extents.digest
            or continuation.parent_allocation_sha256
            != candidate.parent.allocations.digest
            or candidate.parent.custody.extents_digest != parent_extents.digest
            or motif_candidate.parent_snapshot_digest
            != candidate.parent.allocations.digest):
        invalid()
    candidate.__post_init__()
    motif_candidate.__post_init__()
    reconcile_b01_optimizer_manifest(candidate.optimizer, spec, parent_extents)

    proposed = motif_candidate.proposed
    view = motif_candidate.view
    page_count = proposed.manifest.capacity // INITIAL_MOTIF_CAPACITY
    successor_extents = candidate_extents
    if (successor_extents.semantic_bank_count != parent_extents.semantic_bank_count
            or successor_extents.active_semantic_digest
            != parent_extents.active_semantic_digest
            or successor_extents.factor_map_digest != parent_extents.factor_map_digest
            or successor_extents.motif_page_count != page_count
            or successor_extents.motif_key_map_digest != proposed.manifest.digest
            or page_count - parent_extents.motif_page_count
            != view.page_growth.added_pages
            or view.page_growth.candidate_capacity != proposed.manifest.capacity):
        invalid()

    declared = expected_bamf_shapes(spec, successor_extents)
    declared_by_name = {item.name: item for item in declared}
    old_names = set(candidate.optimizer.parameters)
    new_names = set(declared_by_name) - old_names
    expected_new = ({f"motif.page.{parent_extents.motif_page_count}"}
                    if view.page_growth.added_pages else set())
    if new_names != expected_new or old_names - set(declared_by_name):
        invalid()

    parameters = {name: _array_copy(value)
                  for name, value in candidate.optimizer.parameters.items()}
    moments_m = {name: _array_copy(value)
                 for name, value in candidate.optimizer.m.items()}
    moments_v = {name: _array_copy(value)
                 for name, value in candidate.optimizer.v.items()}
    counts = {name: _array_copy(value)
              for name, value in candidate.optimizer.update_counts.items()}
    for name in expected_new:
        item = declared_by_name[name]
        parameters[name] = initialize_bamf_parameter(item, run_seed=run_seed)
        moments_m[name] = np.zeros(item.shape, dtype=np.float32)
        moments_v[name] = np.zeros(item.shape, dtype=np.float32)
        counts[name] = np.zeros(
            declared_update_count_shape(item), dtype=np.uint64)

    for slot in view.plan.allocated:
        page = slot.slot_id // INITIAL_MOTIF_CAPACITY
        row = slot.slot_id % INITIAL_MOTIF_CAPACITY
        name = f"motif.page.{page}"
        if name not in parameters:
            invalid()
        for tree in (parameters, moments_m, moments_v, counts):
            _require_zero_row(tree, name, row)
        parameters[name][row] = initialize_planned_motif_slot(
            view, slot.slot_id, run_seed=run_seed, topology=spec,
            extents=successor_extents)

    optimizer = AdamWStateTree(
        {item.name: mx.array(parameters[item.name], dtype=mx.float32)
         for item in declared},
        {item.name: mx.array(moments_m[item.name], dtype=mx.float32)
         for item in declared},
        {item.name: mx.array(moments_v[item.name], dtype=mx.float32)
         for item in declared},
        {item.name: mx.array(counts[item.name], dtype=mx.uint64)
         for item in declared},
    )
    reconcile_b01_optimizer_manifest(optimizer, spec, successor_extents)
    transition = issue_transition(
        parent_manifest_sha256=candidate.parent.custody.manifest_sha256,
        parent_extents=parent_extents, candidate_extents=successor_extents,
        parent_allocation_sha256=candidate.parent.allocations.digest,
        candidate_allocation_sha256=proposed.digest,
        motif_candidate_sha256=motif_candidate.digest,
        approved_context_sha256=approved.approved_context_digest,
        added_pages=view.page_growth.added_pages,
        source_continuation=continuation)
    return _issue_transaction(
        candidate.parent, optimizer, candidate.teacher_requests_full,
        candidate.update_steps, candidate.step_proofs,
        candidate.training_authorities,
        allocations=proposed, motif_transition=transition)
