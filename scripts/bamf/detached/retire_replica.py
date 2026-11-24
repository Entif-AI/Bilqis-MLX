#!/usr/bin/env python3
"""Retire an explicitly reviewed, completed detached BAMF experiment replica."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

SCHEMA = "bilqis.bamf.detached-long-run/v2"
EVIDENCE = ("bamf-state.json", "events.jsonl", "trainer-observed.json")


def digest(stream):
    result = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        result.update(chunk)
    return result.hexdigest()


def file_digest(path):
    with path.open("rb") as stream:
        return digest(stream)


def write_record(path, record):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def require_idle(pid, target):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        pass
    else:
        raise ValueError(f"receipt PID still exists: {pid}")
    completed = subprocess.run(
        ["lsof", "-nP", "-a", "-u", str(os.getuid()), "-Fn"],
        capture_output=True, text=True, check=False)
    if completed.returncode not in (0, 1) or completed.stderr.strip():
        raise ValueError("cannot establish open-file ownership with lsof")
    prefix = str(target)
    if any(line == "n" + prefix or line.startswith("n" + prefix + "/")
           for line in completed.stdout.splitlines()):
        raise ValueError(f"replica still has open files: {target}")


def allocated_bytes(target):
    total, device = 0, target.stat().st_dev
    for folder, directories, files in os.walk(target, followlinks=False):
        for name in (*directories, *files):
            path = Path(folder) / name
            info = path.lstat()
            if name == ".git" or info.st_dev != device:
                raise ValueError(f"unexpected repository or mount: {path}")
            total += info.st_blocks * 512
    return total


def archive_evidence(target, archive):
    run = target / "run"
    inputs = {name: run / name for name in EVIDENCE if (run / name).exists()}
    if not {"bamf-state.json", "events.jsonl"} <= inputs.keys():
        raise ValueError("missing required run evidence")
    if any(path.is_symlink() or not path.is_file() for path in inputs.values()):
        raise ValueError("unsafe evidence path")
    hashes = {name: file_digest(path) for name, path in inputs.items()}
    temporary = archive.with_suffix(".tmp")
    with tarfile.open(temporary, "w:gz", compresslevel=3) as bundle:
        for name, path in inputs.items():
            bundle.add(path, arcname=name, recursive=False)
    with tarfile.open(temporary, "r:gz") as bundle:
        actual = {member.name: digest(bundle.extractfile(member))
                  for member in bundle.getmembers() if member.isfile()}
    if actual != hashes:
        raise ValueError("evidence archive readback failed")
    os.replace(temporary, archive)
    with archive.open("rb") as stream:
        os.fsync(stream.fileno())
    return hashes


def retire(receipt_path, replica, results, *, apply=False):
    if receipt_path.is_symlink():
        raise ValueError("symlink receipt")
    receipt_path = receipt_path.resolve(strict=True)
    root = receipt_path.parent
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get("schema") != SCHEMA or receipt.get("status") != "PASS"
            or receipt.get("returncode") != 0 or receipt.get("source_mutated") is not False
            or not receipt.get("finished_at")):
        raise ValueError("a completed, successful, immutable-source receipt is required")
    if (Path(receipt["workdir"]).resolve() != root / "source-snapshot"
            or Path(receipt["source_workdir"]).resolve() == root):
        raise ValueError("receipt does not own an isolated experiment root")
    if not replica or replica in {".", "..", "source-snapshot"} or Path(replica).name != replica:
        raise ValueError("replica must be a single explicitly selected child")
    target = root / replica
    archive = root / f"retired-{replica}-evidence.tar.gz"
    record_path = root / f"retired-{replica}.json"
    if target.is_symlink() or archive.is_symlink() or record_path.is_symlink():
        raise ValueError("symlink retirement path")
    result_hashes = {}
    for name in results:
        path = root / name
        if Path(name).name != name or path.is_symlink() or not path.is_file() or not path.stat().st_size:
            raise ValueError(f"missing or unsafe result: {name}")
        result_hashes[name] = file_digest(path)
    log = Path(receipt["log"]).resolve(strict=True)
    if log.parent != root or not log.is_file():
        raise ValueError("missing isolated run log")
    result_hashes[log.name] = file_digest(log)
    if not target.exists():
        previous = json.loads(record_path.read_text())
        if previous["archive_sha256"] != file_digest(archive):
            raise ValueError("retired evidence digest drift")
        if previous["status"] == "PREPARED" and apply:
            previous["status"] = "RETIRED"
            write_record(record_path, previous)
        return previous
    if (not target.is_dir() or not (target / "plane.sqlite3").is_file()
            or not (target / "run/bamf-state.json").is_file()
            or (target / "run").is_symlink()):
        raise ValueError("not an isolated learner replica")
    require_idle(receipt["pid"], target)
    record = {
        "status": "DRY_RUN", "replica": str(target),
        "allocated_bytes": allocated_bytes(target),
        "receipt_sha256": file_digest(receipt_path),
        "source_sha256": receipt["source_sha256"],
        "snapshot_sha256": receipt["snapshot_sha256"],
        "result_sha256": result_hashes,
    }
    if not apply:
        return record
    record["evidence_sha256"] = archive_evidence(target, archive)
    record["archive_sha256"] = file_digest(archive)
    require_idle(receipt["pid"], target)
    record["status"] = "PREPARED"
    write_record(record_path, record)
    shutil.rmtree(target)
    record["status"] = "RETIRED"
    record["evidence_bytes"] = archive.stat().st_size
    write_record(record_path, record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--replica", required=True)
    parser.add_argument("--result", action="append", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(retire(args.receipt, args.replica, args.result, apply=args.apply),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
