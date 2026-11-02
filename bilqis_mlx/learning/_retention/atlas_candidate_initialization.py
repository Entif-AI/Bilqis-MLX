"""B12.2 B01 initialization, seed witnesses, and motif materialization replay."""
from __future__ import annotations

from dataclasses import dataclass

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_engram import (
    INITIAL_MOTIF_CAPACITY, initialize_planned_motif_slot,
)
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree
from bilqis_mlx.runtime.model_topology_v2 import (
    FEATURE_NONE_ROW, GenerationExtents, Initializer, ModelTopologySpecV2,
    expected_bamf_shapes, initialize_bamf_parameter, validate_bamf_parameters,
)

INITIALIZATION_SCHEMA = 'bilqis.mlx.candidate-initialization-binding/v1'


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


@dataclass(frozen=True)
class CandidateInitialization:
    """B01 initialization authority carried by candidate-owned descendants."""

    topology: ModelTopologySpecV2
    extents: GenerationExtents
    run_seed: int
    schema_version: str = INITIALIZATION_SCHEMA

    def __post_init__(self):
        if (type(self.topology) is not ModelTopologySpecV2
                or type(self.extents) is not GenerationExtents
                or type(self.run_seed) is not int
                or self.schema_version != INITIALIZATION_SCHEMA):
            _invalid()


def same_optimizer(left: AdamWStateTree, right: AdamWStateTree) -> bool:
    """Compare complete optimizer custody exactly, including moments and counts."""
    left.validate()
    right.validate()
    for field in ('parameters', 'm', 'v', 'update_counts'):
        first, second = getattr(left, field), getattr(right, field)
        if set(first) != set(second):
            return False
        if any(not bool(mx.array_equal(first[name], second[name])) for name in first):
            return False
    return True


def verify_seed_from_untouched_b01_state(
    optimizer: AdamWStateTree,
    topology: ModelTopologySpecV2,
    extents: GenerationExtents,
    run_seed: int,
) -> None:
    """Re-prove a carried seed from B01 regions with zero update counts.

    Candidate metadata is not provenance authority. A future motif allocation
    may consume its retained seed only while at least one seed-sensitive B01
    scalar or row remains untouched and exactly matches B01 replay. If no such
    witness remains, this bounded owner fails closed.
    """
    seed_sensitive = {
        Initializer.MATRIX, Initializer.EMBEDDING, Initializer.FEATURE_TABLE,
    }
    witnessed = False
    for item in expected_bamf_shapes(topology, extents):
        if item.initializer not in seed_sensitive:
            continue
        actual = optimizer.parameters[item.name]
        counts = optimizer.update_counts[item.name]
        expected = mx.array(
            initialize_bamf_parameter(item, run_seed=run_seed), dtype=mx.float32)
        if counts.ndim == 0:
            if int(counts) == 0:
                witnessed = True
                if not bool(mx.array_equal(actual, expected)):
                    _invalid()
            continue
        if counts.ndim != 1 or actual.ndim < 1 or counts.shape[0] != actual.shape[0]:
            _invalid()
        for row in range(counts.shape[0]):
            if item.initializer is Initializer.FEATURE_TABLE and row == FEATURE_NONE_ROW:
                # B01 fixes NONE to zero for every run seed; it cannot
                # discriminate which seed initialized this retained tree.
                continue
            if int(counts[row]) == 0:
                witnessed = True
                if not bool(mx.array_equal(actual[row], expected[row])):
                    _invalid()
    if not witnessed:
        _invalid()


def materialize_planned_motif_rows(parent, proposal) -> AdamWStateTree:
    """Replay B01 initialization for newly allocated in-page motif rows."""
    binding = parent.initialization
    if (type(binding) is not CandidateInitialization
            or type(binding.topology) is not ModelTopologySpecV2
            or type(binding.extents) is not GenerationExtents
            or type(binding.run_seed) is not int
            or binding.extents.active_semantic_digest != parent.allocations.manifest.semantic_release
            or binding.extents.motif_page_count * INITIAL_MOTIF_CAPACITY
            != parent.allocations.manifest.capacity
            or proposal.view.page_growth.added_pages != 0):
        _invalid()
    validate_bamf_parameters(
        binding.topology, binding.extents, parent.optimizer.parameters)
    verify_seed_from_untouched_b01_state(
        parent.optimizer, binding.topology, binding.extents, binding.run_seed)
    allocated = proposal.view.plan.allocated
    if not allocated:
        return parent.optimizer

    parameters = dict(parent.optimizer.parameters)
    first = dict(parent.optimizer.m)
    second = dict(parent.optimizer.v)
    counts = dict(parent.optimizer.update_counts)
    touched = {}
    for slot in allocated:
        page = slot.slot_id // INITIAL_MOTIF_CAPACITY
        row = slot.slot_id % INITIAL_MOTIF_CAPACITY
        name = f"motif.page.{page}"
        if name not in parameters or counts[name].shape != (INITIAL_MOTIF_CAPACITY,):
            _invalid()
        if name not in touched:
            touched[name] = (
                mx.array(parameters[name]), mx.array(first[name]),
                mx.array(second[name]), mx.array(counts[name]),
            )
        parameter, m, v, count = touched[name]
        parameter[row] = mx.array(initialize_planned_motif_slot(
            proposal.view, slot.slot_id, run_seed=binding.run_seed,
            topology=binding.topology, extents=binding.extents), dtype=mx.float32)
        m[row] = 0
        v[row] = 0
        count[row] = mx.array(0, dtype=mx.uint64)
    for name, values in touched.items():
        parameters[name], first[name], second[name], counts[name] = values
    mx.eval(parameters, first, second, counts)
    return AdamWStateTree(parameters, first, second, counts)
