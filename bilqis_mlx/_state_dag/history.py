"""Historical state migration and state-DAG command-line entrypoint."""
from __future__ import annotations

import json
import os
from pathlib import Path

from bilqis_mlx.data_plane import data_plane
from .contracts import StateDagError, _FIELD_CACHE, _canonical
from .nodes import _read_pointer, _write_node
from .persistence import head_summary, migrate_current_head

def _facade():
    import bilqis_mlx.state_dag as facade
    return facade

def _durable(*args, **kwargs):
    return _facade()._durable(*args, **kwargs)

def read_current(*args, **kwargs):
    return _facade().read_current(*args, **kwargs)

def read_generation(*args, **kwargs):
    return _facade().read_generation(*args, **kwargs)

def _generation_numbers(run_dir: Path) -> tuple[int, ...]:
    states = Path(run_dir) / "states"
    numbers = set()
    for path in states.iterdir():
        name = path.name
        stem = (name[:-8] if name.endswith(".json.gz") else
                name[:-12] if name.endswith(".json.sha256") else
                name[:-5] if name.endswith(".json") else None)
        if stem is not None and stem.isdecimal():
            numbers.add(int(stem))
    return tuple(sorted(numbers))

def migrate_history(run_dir: Path, *, max_files: int = 0) -> dict:
    """Move legacy full-copy generation receipts into the immutable shared DAG."""
    if type(max_files) is not int or max_files < 0:
        raise ValueError(StateDagError.HISTORY_MIGRATION_BUDGET_INVALID.value)
    run_dir = Path(run_dir)
    current = read_current(run_dir)
    current_generation = current["generation"]
    migrated = reclaimed = 0
    parent = None
    for generation in _generation_numbers(run_dir):
        if generation > current_generation:
            break
        path = run_dir / "states" / f"{generation:07d}.json"
        zipped = run_dir / "states" / f"{generation:07d}.json.gz"
        proof = run_dir / "states" / f"{generation:07d}.json.sha256"
        pointer = _read_pointer(path)
        if pointer is not None:
            parent = pointer["node_sha256"]
            for stale in (zipped, proof):
                if stale.exists() and not stale.is_symlink():
                    reclaimed += stale.stat().st_size
                    stale.unlink()
            continue
        if max_files and migrated >= max_files:
            break
        receipt = read_generation(run_dir, generation)
        old_bytes = sum(
            item.stat().st_size for item in (path, zipped, proof)
            if item.exists() and not item.is_symlink())
        with data_plane().transaction():
            pointer, fields, normalized = _write_node(
                run_dir, receipt, parent=parent)
        if normalized != receipt:
            raise ValueError(StateDagError.HISTORY_NORMALIZATION_DRIFT.value)
        _durable(path, _canonical(pointer), replace=path.exists())
        if read_generation(run_dir, generation) != normalized:
            raise ValueError(StateDagError.HISTORY_READBACK_DRIFT.value)
        if generation == current_generation:
            _durable(run_dir / "state.json", _canonical(pointer), replace=True)
            _FIELD_CACHE[str(run_dir.resolve())] = {
                key: (normalized[key], spec) for key, spec in fields.items()}
        for stale in (zipped, proof):
            if stale.exists():
                if stale.is_symlink() or not stale.is_file():
                    raise ValueError(StateDagError.HISTORY_STALE_ARTIFACT_UNSAFE.value)
                stale.unlink()
        new_bytes = path.stat().st_size
        reclaimed += max(0, old_bytes - new_bytes)
        migrated += 1
        parent = pointer["node_sha256"]
    if migrated:
        directory = os.open(run_dir / "states", os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    return {
        "migrated_generations": migrated,
        "estimated_reclaimed_bytes": reclaimed,
        "current_generation": current_generation,
    }

def main(argv=None) -> int:
    """Migrate or inspect the current run's state head without neural mutation."""
    import argparse
    import fcntl
    from .paths import active_run_dir

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("status", "migrate"):
        command = sub.add_parser(name)
        command.add_argument("--run-dir", type=Path, default=active_run_dir())
    history = sub.add_parser("migrate-history")
    history.add_argument("--run-dir", type=Path, default=active_run_dir())
    history.add_argument("--max-files", type=int, default=0,
                         help="0 migrates every legacy generation")
    args = parser.parse_args(argv)
    root = args.run_dir.expanduser().resolve(strict=True)
    if args.action == "status":
        print(json.dumps({**head_summary(root), "data_plane": data_plane().stats()},
                         sort_keys=True))
        return 0

    lock = root / ".grade-a-operator.lock"
    if lock.is_symlink():
        raise ValueError(StateDagError.OPERATOR_LOCK_UNSAFE.value)
    with lock.open("a+b") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(StateDagError.HUMAN_TRAINING_ACTIVE.value) from None
        if args.action == "migrate-history":
            receipt = migrate_current_head(root)
            result = migrate_history(root, max_files=args.max_files)
            print(json.dumps({**result, "generation": receipt["generation"],
                              "data_plane": data_plane().stats()}, sort_keys=True))
        else:
            before = head_summary(root)
            receipt = migrate_current_head(root)
            after = head_summary(root)
            print(json.dumps({
                "mode": "MIGRATED" if before["mode"] != after["mode"] else "ALREADY_MIGRATED",
                "generation": receipt["generation"],
                "before": before,
                "after": after,
                "data_plane": data_plane().stats(),
            }, sort_keys=True))
    return 0

