"""Bounded recovery for the SQLite accepted-authority tip and filesystem pointer."""
from __future__ import annotations

from pathlib import Path

from ..codec import load_bamf_bundle
from ..records import BAMF_POINTER_SCHEMA, canonical, invalid, sha
from .acceptance import (
    require_checkpoint_published_acceptance, require_published_acceptance,
)
from .accepted_authority_checkpoint import read_protected_accepted_authority_tip
from .events import reconcile_bamf_outbox
from .storage import (
    _atomic_pointer, _live_bundle_manifest, _pointer_lock, _read_pointer,
)


def _pointer_from_checkpoint(run_dir: Path, checkpoint) -> dict:
    pointer = {
        "schema": BAMF_POINTER_SCHEMA,
        "run_id": checkpoint.run_id,
        "generation": checkpoint.generation,
        "parent_manifest_sha256": checkpoint.parent_manifest_sha256,
        "bundle": f"bamf-bundles/{checkpoint.manifest_sha256}",
        "manifest_sha256": checkpoint.manifest_sha256,
        "acceptance_sha256": checkpoint.acceptance_sha256,
    }
    if sha(canonical(pointer)) != checkpoint.pointer_sha256:
        invalid("BAMF_ACCEPTED_AUTHORITY_TIP_DRIFT")
    return pointer


def _pointer_matches_checkpoint(pointer: dict, checkpoint) -> bool:
    return (
        pointer.get("run_id") == checkpoint.run_id
        and pointer.get("generation") == checkpoint.generation
        and pointer.get("manifest_sha256") == checkpoint.manifest_sha256
        and pointer.get("acceptance_sha256") == checkpoint.acceptance_sha256
        and sha(canonical(pointer)) == checkpoint.pointer_sha256
    )


def _recover_tip_ahead_locked(run_dir: Path, pointer, checkpoint):
    if pointer is not None and _pointer_matches_checkpoint(pointer, checkpoint):
        return pointer
    if pointer is None:
        if checkpoint.generation != 0 or checkpoint.parent_manifest_sha256 is not None:
            invalid("BAMF_ACCEPTED_AUTHORITY_TIP_DRIFT")
    elif (checkpoint.generation != pointer.get("generation", -1) + 1
          or checkpoint.parent_manifest_sha256 != pointer.get("manifest_sha256")
          or checkpoint.parent_acceptance_sha256 != pointer.get("acceptance_sha256")):
        invalid("BAMF_ACCEPTED_AUTHORITY_TIP_DRIFT")

    child_pointer = _pointer_from_checkpoint(run_dir, checkpoint)
    child = load_bamf_bundle(
        run_dir / "bamf-bundles" / checkpoint.manifest_sha256,
        expected_manifest_sha256=checkpoint.manifest_sha256)
    if (child.run_id != checkpoint.run_id
            or child.generation != checkpoint.generation
            or child.parent_manifest_sha256 != checkpoint.parent_manifest_sha256):
        invalid("BAMF_ACCEPTED_AUTHORITY_TIP_DRIFT")
    require_checkpoint_published_acceptance(
        run_dir, child_pointer, child, checkpoint,
        live_manifest=_live_bundle_manifest)
    _atomic_pointer(run_dir / "bamf-state.json", child_pointer)
    reconcile_bamf_outbox(run_dir, child)
    return child_pointer


def recover_accepted_authority_pointer(run_dir: Path):
    """Reconcile only the exact crash state where protected tip is one epoch ahead.

    A stale or rolled-back pointer is never accepted as current.  The only mutable
    recovery performed here is forward installation of the exact pointer already
    committed by the protected B13 tip.
    """
    run_dir = Path(run_dir)
    with _pointer_lock(run_dir, create=True):
        pointer = _read_pointer(run_dir / "bamf-state.json")
        run_id = pointer.get("run_id") if pointer is not None else None
        if run_id is None:
            # Pointerless genesis recovery cannot infer a run identifier from the
            # filesystem.  Its prepared/sealed recovery owner supplies that path.
            return pointer
        tip = read_protected_accepted_authority_tip(run_id)
        if tip is None:
            if pointer.get("generation") == 0:
                student = load_bamf_bundle(
                    run_dir / "bamf-bundles" / pointer["manifest_sha256"],
                    expected_manifest_sha256=pointer["manifest_sha256"])
                require_published_acceptance(
                    run_dir, pointer, student, load_bundle=load_bamf_bundle,
                    live_manifest=_live_bundle_manifest)
            invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_REQUIRED")
        return _recover_tip_ahead_locked(run_dir, pointer, tip)


def recover_known_run_accepted_authority_pointer(run_dir: Path, run_id: str):
    """Pointerless-capable variant used by generation-zero recovery/publication."""
    run_dir = Path(run_dir)
    with _pointer_lock(run_dir, create=True):
        pointer = _read_pointer(run_dir / "bamf-state.json")
        if pointer is not None and pointer.get("run_id") != run_id:
            invalid("BAMF_ACCEPTED_AUTHORITY_TIP_DRIFT")
        tip = read_protected_accepted_authority_tip(run_id)
        if tip is None:
            return pointer
        return _recover_tip_ahead_locked(run_dir, pointer, tip)


__all__ = (
    "recover_accepted_authority_pointer",
    "recover_known_run_accepted_authority_pointer",
)
