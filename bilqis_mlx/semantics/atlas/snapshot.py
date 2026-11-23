"""Verified, database-free readback for immutable semantic Atlas artifacts."""
from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar

from ..atlas_projection import FrozenAtlasSnapshot
from bilqis_mlx.b11_observation import note_atlas_reload
from .snapshot_contracts import (
    AtlasArtifactIdentity, AtlasArtifactSelection, _require_registered_source_pin,
    resolve_atlas_artifact_selection,
)
from .snapshot_materialize import load_atlas_snapshot

_PROCESS_OWNED_SNAPSHOT = ContextVar(
    "bilqis_process_owned_atlas_snapshot", default=None)


@contextmanager
def reuse_pinned_atlas_snapshot(
        selection: AtlasArtifactSelection, snapshot: FrozenAtlasSnapshot):
    """Reuse one already-authenticated immutable pin inside an owner-scoped operation."""
    if (type(selection) is not AtlasArtifactSelection
            or type(snapshot) is not FrozenAtlasSnapshot):
        raise TypeError("ATLAS_PROCESS_SNAPSHOT_REUSE_INVALID")
    token = _PROCESS_OWNED_SNAPSHOT.set((selection, snapshot))
    try:
        yield snapshot
    finally:
        _PROCESS_OWNED_SNAPSHOT.reset(token)


def load_pinned_atlas_snapshot(selection: AtlasArtifactSelection) -> FrozenAtlasSnapshot:
    """Reload a source artifact only under an independently governed A01 pin."""
    owned = _PROCESS_OWNED_SNAPSHOT.get()
    if owned is not None and selection == owned[0]:
        return owned[1]
    note_atlas_reload()
    _require_registered_source_pin(selection)
    return load_atlas_snapshot(
        selection.path,
        expected_bundle_id=selection.bundle_id,
        expected_release_sha256=selection.release_sha256,
        expected_source_bundle_id=selection.source_bundle_id,
    )


__all__ = (
    "AtlasArtifactIdentity",
    "AtlasArtifactSelection",
    "load_atlas_snapshot",
    "load_pinned_atlas_snapshot",
    "reuse_pinned_atlas_snapshot",
    "resolve_atlas_artifact_selection",
)
