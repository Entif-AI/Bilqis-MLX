"""Test-only construction of sealed B02 active-row records from known fixtures."""
from bilqis_mlx.runtime.atlas_model_contracts import _issue_bamf_active_semantic_rows


def active_semantic_rows(compiled, active_indices, *, run_id="test-b02", generation=0):
    return _issue_bamf_active_semantic_rows(
        run_id, generation, compiled.extents, compiled.features, tuple(active_indices))


def snapshot_active_semantic_rows(compiled, snapshot, *, run_id="test-b02", generation=0):
    return active_semantic_rows(
        compiled,
        tuple(entry.index for entry in snapshot.abi_entries if entry.active),
        run_id=run_id,
        generation=generation,
    )
