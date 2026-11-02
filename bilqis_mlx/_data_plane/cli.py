"""Shared workstation data plane for immutable state and integrity cache."""
from __future__ import annotations
import json
import time
from pathlib import Path
from .contracts import DataPlaneError, _error

def _facade():
    import bilqis_mlx.data_plane as facade
    return facade
def data_plane(*args, **kwargs): return _facade().data_plane(*args, **kwargs)
def dedupe_bundle_payloads(*args, **kwargs): return _facade().dedupe_bundle_payloads(*args, **kwargs)
def sync_event_ledger(*args, **kwargs): return _facade().sync_event_ledger(*args, **kwargs)
def referenced_custody_files(*args, **kwargs): return _facade().referenced_custody_files(*args, **kwargs)
def verify_file_digest(*args, **kwargs): return _facade().verify_file_digest(*args, **kwargs)

def main(argv=None) -> int:
    """Inspect or prewarm the shared workstation data plane."""
    import argparse
    import fcntl
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "status", "warm-custody", "warm-events", "dedupe-bundles"))
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args(argv)
    if args.action == "status":
        print(json.dumps(data_plane().stats(), sort_keys=True))
        return 0
    if args.run_dir is None:
        from .paths import active_run_dir
        root = active_run_dir().expanduser().resolve(strict=True)
    else:
        root = args.run_dir.expanduser().resolve(strict=True)
    lock = root / ".grade-a-operator.lock"
    if lock.is_symlink():
        raise ValueError(DataPlaneError.OPERATOR_LOCK_UNSAFE.value)
    with lock.open("a+b") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(DataPlaneError.HUMAN_TRAINING_ACTIVE.value) from None
        if args.action == "dedupe-bundles":
            print(json.dumps(dedupe_bundle_payloads(root), sort_keys=True))
            return 0
        if args.action == "warm-events":
            started = time.perf_counter()
            result = sync_event_ledger(root)
            print(json.dumps({**result,
                              "mode": "EVENT_LEDGER_INDEX_WARMED",
                              "elapsed_seconds": round(
                                  time.perf_counter() - started, 3)}, sort_keys=True))
            return 0
        from .state_dag import read_current
        before = data_plane().stats()
        started = time.perf_counter()
        files = referenced_custody_files(root, read_current(root))
        for path, expected in files:
            if path.is_symlink() or not path.is_file():
                raise ValueError(_error(DataPlaneError.CUSTODY_ARTIFACT_MISSING, path))
            if not verify_file_digest(path, expected):
                raise ValueError(_error(DataPlaneError.CUSTODY_DIGEST_DRIFT, path))
        after = data_plane().stats()
        print(json.dumps({
            "mode": "CUSTODY_CACHE_WARMED",
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "referenced_files": len(files),
            "verified_before": before["verified_files"],
            "verified_after": after["verified_files"],
            "data_plane": after,
        }, sort_keys=True))
        return 0
    raise AssertionError(args.action)
