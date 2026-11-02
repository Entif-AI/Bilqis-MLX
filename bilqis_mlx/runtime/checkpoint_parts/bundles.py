"""Stage, verify and quarantine complete own-AdamW checkpoint bundles."""
from __future__ import annotations

import bilqis_mlx.learning.champions as _learning_champions
import bilqis_mlx.runtime.mlx_checkpoint as _runtime_mlx_checkpoint
import bilqis_mlx.source as _bilqis_mlx_source
import os as _os
import pathlib as _pathlib

from .journal import _record

_UNSAFE_STAGING_ROOT = "HUMAN_TRAINER_UNSAFE_STAGING_ROOT"
_UNSAFE_BUNDLE_QUARANTINE = "HUMAN_TRAINER_UNSAFE_BUNDLE_QUARANTINE"
_QUARANTINE_IDENTITY_COLLISION = "HUMAN_TRAINER_QUARANTINE_IDENTITY_COLLISION"
_UNCOMMITTED_BUNDLE_UNSAFE_PATH = "HUMAN_TRAINER_UNCOMMITTED_BUNDLE_UNSAFE_PATH"


def _bundle_pointer(run_dir: _pathlib.Path, name: str, parameters, optimizer, graph,
                    *, reserve_gib: float, model_topology=None):
    stage_root = run_dir / ".bundle-staging"
    if stage_root.is_symlink() or (stage_root.exists() and not stage_root.is_dir()):
        raise ValueError(_UNSAFE_STAGING_ROOT)
    stage_root.mkdir(exist_ok=True)
    stage_directory = stage_root / name
    directory = run_dir / "bundles" / name
    if directory.exists() or directory.is_symlink():
        raise ValueError("HUMAN_TRAINER_BUNDLE_ALREADY_PUBLISHED")
    metadata = _runtime_mlx_checkpoint.save_new_bundle(
        stage_directory, parameters, optimizer, source_digest=_bilqis_mlx_source.AUDITED_PARENT.sha256,
        semantic_catalog=graph, reserve_gib=reserve_gib, model_topology=model_topology)
    restored, restored_optimizer, manifest, restored_graph = (
        _runtime_mlx_checkpoint.load_semantically_bound_bundle(stage_directory))
    if (metadata != manifest or restored_graph != graph or
            list(restored) != list(parameters) or
            int(restored_optimizer.state["step"].item()) != int(optimizer.state["step"].item())):
        raise ValueError("HUMAN_TRAINER_COMPLETE_CHECKPOINT_READBACK_DRIFT")
    for filename in ("model-and-own-adamw.safetensors",
                     "semantic-catalog.json", "manifest.json"):
        fd = _os.open(stage_directory / filename, _os.O_RDONLY)
        try:
            _os.fsync(fd)
        finally:
            _os.close(fd)
    dir_fd = _os.open(stage_directory, _os.O_RDONLY)
    try:
        _os.fsync(dir_fd)
    finally:
        _os.close(dir_fd)
    directory.parent.mkdir(exist_ok=True)
    # The published bundles namespace must contain ONLY complete, read-back
    # verified three-file bundles. Failed writes remain in isolated staging.
    stage_directory.rename(directory)
    fd = _os.open(directory.parent, _os.O_RDONLY)
    try:
        _os.fsync(fd)
    finally:
        _os.close(fd)
    stage_root.rmdir()
    return _learning_champions.Checkpoint(metadata["safetensors_sha256"],
                      str(directory.relative_to(run_dir)),
                      metadata["optimizer_step"], True)


def _clean_staged_bundles(run_dir: _pathlib.Path) -> dict[str, tuple[str, ...]]:
    """Reconcile unpublished bundles without losing a possibly valid student."""
    stage = run_dir / ".bundle-staging"
    if not stage.exists() and not stage.is_symlink():
        return {"discarded": (), "quarantined": ()}
    if stage.is_symlink() or not stage.is_dir():
        raise ValueError(_UNSAFE_STAGING_ROOT)
    expected = {"model-and-own-adamw.safetensors", "semantic-catalog.json",
                "manifest.json"}
    discarded, quarantined = [], []
    for folder in stage.iterdir():
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError("HUMAN_TRAINER_UNKNOWN_STAGED_BUNDLE")
        files = list(folder.iterdir())
        if any(file.is_symlink() or not file.is_file() or file.name not in expected
               for file in files):
            raise ValueError("HUMAN_TRAINER_UNKNOWN_STAGED_BUNDLE_CONTENT")
        if (folder / "model-and-own-adamw.safetensors").exists():
            # Even if its manifest is incomplete, this is the only surviving
            # binary for updates possibly completed just before a crash. Keep
            # it outside active bundles for human custody recovery.
            custody = run_dir / ".bundle-quarantine"
            if custody.is_symlink() or (custody.exists() and not custody.is_dir()):
                raise ValueError(_UNSAFE_BUNDLE_QUARANTINE)
            custody.mkdir(exist_ok=True)
            target = custody / folder.name
            if target.exists() or target.is_symlink():
                raise ValueError(_QUARANTINE_IDENTITY_COLLISION)
            folder.rename(target)
            quarantined.append(folder.name)
        else:
            for file in files:
                file.unlink()
            folder.rmdir()
            discarded.append(folder.name)
    stage.rmdir()
    return {"discarded": tuple(discarded), "quarantined": tuple(quarantined)}


def _quarantine_newer_uncommitted_bundles(run_dir: _pathlib.Path, retained: set[str],
                                          current_optimizer_step: int) -> tuple[str, ...]:
    """Never prune a post-update model published before its pointer crashed."""
    root = run_dir / "bundles"
    if not root.exists():
        return ()
    if root.is_symlink() or not root.is_dir():
        raise ValueError(_UNCOMMITTED_BUNDLE_UNSAFE_PATH)
    quarantined = []
    for candidate in sorted(root.iterdir()):
        if candidate.name == ".DS_Store" and not candidate.is_symlink() and candidate.is_file():
            # Keep Finder's bookkeeping from aborting an otherwise valid
            # human-run checkpoint transaction. Never touch model files.
            candidate.unlink()
            continue
        relative = "bundles/" + candidate.name
        if relative in retained:
            continue
        if candidate.is_symlink() or not candidate.is_dir():
            raise ValueError(_UNCOMMITTED_BUNDLE_UNSAFE_PATH)
        weights, own_adamw, metadata, graph = _runtime_mlx_checkpoint.load_semantically_bound_bundle(candidate)
        if (metadata["source_digest"] != _bilqis_mlx_source.AUDITED_PARENT.sha256 or
                metadata["optimizer_step"] < 0):
            raise ValueError("HUMAN_TRAINER_UNCOMMITTED_BUNDLE_SOURCE_DRIFT")
        del weights, own_adamw, graph
        if metadata["optimizer_step"] <= current_optimizer_step:
            continue
        target_parent = run_dir / ".bundle-quarantine"
        if target_parent.is_symlink() or (target_parent.exists() and
                                          not target_parent.is_dir()):
            raise ValueError(_UNSAFE_BUNDLE_QUARANTINE)
        target_parent.mkdir(exist_ok=True)
        target = target_parent / candidate.name
        if target.exists() or target.is_symlink():
            raise ValueError(_QUARANTINE_IDENTITY_COLLISION)
        candidate.rename(target)
        quarantined.append(candidate.name)
        fd = _os.open(target_parent, _os.O_RDONLY)
        try:
            _os.fsync(fd)
        finally:
            _os.close(fd)
        _record(run_dir, {"event": "SCHOOL_NEWER_UNCOMMITTED_BUNDLE_QUARANTINED",
                          "grade": "A", "filename": str(target.relative_to(run_dir)),
                          "optimizer_step": metadata["optimizer_step"],
                          "student_sha256": metadata["safetensors_sha256"],
                          "prior_committed_optimizer_step": current_optimizer_step})
    return tuple(quarantined)
