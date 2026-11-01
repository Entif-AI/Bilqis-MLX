"""B12.2 proof that a carried run seed still matches untouched B01 state."""
from __future__ import annotations

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents, Initializer, ModelTopologySpecV2, expected_bamf_shapes,
    initialize_bamf_parameter,
)


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


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
            if int(counts[row]) == 0:
                witnessed = True
                if not bool(mx.array_equal(actual[row], expected[row])):
                    _invalid()
    if not witnessed:
        _invalid()
