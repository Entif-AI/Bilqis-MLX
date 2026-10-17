"""Lossless, verified compression of superseded immutable school generations.

Only old JSON state snapshots are compacted. Checkpoints, AdamW, frozen
soups, current/near-current generations and curriculum-transition evidence
are never pruned. The original bytes remain readable with SHA-256 custody.
"""
from __future__ import annotations

import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _regular(path: Path) -> bool:
    if path.is_symlink():
        raise ValueError("STATE_ARCHIVE_SYMLINK_FORBIDDEN:" + str(path))
    return path.is_file()


def _durable(path: Path, content: bytes) -> None:
    if _regular(path):
        if path.read_bytes() != content:
            raise ValueError("STATE_ARCHIVE_EXISTING_CONTENT_DRIFT")
        return
    fd, temp = tempfile.mkstemp(prefix=".state-archive-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists() or path.is_symlink():
            raise ValueError("STATE_ARCHIVE_DESTINATION_COLLISION")
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def read_generation(run_dir: Path, generation: int) -> dict:
    """Read either original JSON or verified compressed JSON transparently."""
    if type(generation) is not int or generation < 0:
        raise ValueError("STATE_ARCHIVE_GENERATION_INVALID")
    folder = Path(run_dir) / "states"
    original = folder / f"{generation:07d}.json"
    zipped = folder / f"{generation:07d}.json.gz"
    proof = folder / f"{generation:07d}.json.sha256"
    if _regular(original):
        data = original.read_bytes()
    else:
        if not _regular(zipped) or not _regular(proof):
            raise ValueError("STATE_ARCHIVE_GENERATION_NOT_FOUND")
        # Every zipped snapshot has a separate SHA over the *original* bytes.
        with gzip.open(zipped, "rb") as stream:
            data = stream.read()
        if _sha(data) != proof.read_text(encoding="ascii").strip():
            raise ValueError("STATE_ARCHIVE_GENERATION_SHA_DRIFT")
    value = json.loads(data)
    if value.get("generation") != generation:
        raise ValueError("STATE_ARCHIVE_GENERATION_DRIFT")
    return value


def _gzip(data: bytes) -> bytes:
    import io
    out = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", compresslevel=6,
                       mtime=0, fileobj=out) as stream:
        stream.write(data)
    return out.getvalue()


def compact_states(run_dir: Path, *, keep_latest: int = 4,
                   max_files: int = 128) -> dict:
    """Archive eligible generations. Caller holds the human operator lock."""
    if keep_latest < 3 or max_files < 0:
        raise ValueError("STATE_ARCHIVE_INVALID_BUDGET")
    root = Path(run_dir)
    latest_path = root / "state.json"
    if not _regular(latest_path):
        raise ValueError("STATE_ARCHIVE_LATEST_STATE_MISSING")
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    generation = latest["generation"]
    if read_generation(root, generation) != latest:
        raise ValueError("STATE_ARCHIVE_LATEST_IMMUTABLE_DRIFT")
    protected = {
        str(item.get("state_file", ""))
        for item in latest.get("curriculum_history", ())
    }
    snapshots = root / "states"
    archived = 0
    bytes_before = bytes_after = 0
    for old in sorted(snapshots.glob("*.json")):
        if max_files and archived >= max_files:
            break
        if not _regular(old):
            continue
        try:
            number = int(old.stem)
        except ValueError:
            raise ValueError("STATE_ARCHIVE_UNKNOWN_STATE_FILENAME") from None
        if (number >= generation - keep_latest + 1 or
                f"states/{old.name}" in protected):
            continue
        data = old.read_bytes()
        if json.loads(data).get("generation") != number:
            raise ValueError("STATE_ARCHIVE_SOURCE_GENERATION_DRIFT")
        proof = old.with_name(old.name + ".sha256")
        zipped = old.with_name(old.name + ".gz")
        _durable(proof, (_sha(data) + "\n").encode("ascii"))
        _durable(zipped, _gzip(data))
        with gzip.open(zipped, "rb") as stream:
            if stream.read() != data:
                raise ValueError("STATE_ARCHIVE_READBACK_DRIFT")
        if read_generation(root, number) != json.loads(data):
            raise ValueError("STATE_ARCHIVE_READBACK_GENERATION_DRIFT")
        old.unlink()
        archived += 1
        bytes_before += len(data)
        bytes_after += zipped.stat().st_size + proof.stat().st_size
    if archived:
        directory = os.open(snapshots, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    return {"compressed_generations": archived,
            "original_bytes": bytes_before,
            "archived_bytes": bytes_after,
            "estimated_saved_bytes": bytes_before - bytes_after,
            "current_generation_preserved": generation}


def main(argv=None) -> int:
    from .paths import active_run_dir
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=active_run_dir())
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--max-files", type=int, default=128,
                        help="0 compresses every eligible old generation")
    args = parser.parse_args(argv)
    root = args.run_dir.expanduser().resolve(strict=True)
    if not args.apply:
        latest = json.loads((root / "state.json").read_text())
        candidates = sum(1 for p in (root / "states").glob("*.json")
                         if p.stem.isdecimal() and
                         int(p.stem) < latest["generation"] - 3)
        print(json.dumps({"mode": "PLAN_ONLY", "candidates_at_most": candidates,
                          "run_dir": str(root)}))
        return 0
    lock = root / ".grade-a-operator.lock"
    if lock.is_symlink():
        raise ValueError("STATE_ARCHIVE_OPERATOR_LOCK_UNSAFE")
    with lock.open("a+b") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("STATE_ARCHIVE_HUMAN_TRAINING_ACTIVE") from None
        print(json.dumps(compact_states(root, max_files=args.max_files)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
