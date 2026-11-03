"""B13-owned source continuation from immutable retained-generation custody."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.learning.atlas_engram_source import (
    _prepare_source_qualified_motifs_with_parent,
)
from bilqis_mlx.runtime.bamf_bundle.codec import load_bamf_bundle


def continue_source_qualified_motifs_from_bundle(
        source_adapter, row, atlas_selection, *, retained_bundle_root: str | Path,
        expected_manifest_sha256: str, source_root, graph, task_scope,
        source_frontier, policy, source_seed: int, source_each: int, budget,
        source_profile_parameters=None, course=None):
    """Continue B07 planning only from one exact custody-validated bundle."""
    student = load_bamf_bundle(
        Path(retained_bundle_root),
        expected_manifest_sha256=expected_manifest_sha256,
    )
    return _prepare_source_qualified_motifs_with_parent(
        source_adapter, row, atlas_selection,
        source_root=source_root, graph=graph, task_scope=task_scope,
        source_frontier=source_frontier, policy=policy,
        source_seed=source_seed, source_each=source_each, budget=budget,
        parent=student.retained_state.allocations,
        source_profile_parameters=source_profile_parameters, course=course,
    )
