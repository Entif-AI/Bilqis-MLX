#!/usr/bin/env python3
"""Plan or explicitly APFS-clone a *stopped* saved Bilqis run for trials.

No source deletion, live trainer invocation, optimizer step, or existing-target
overwrite. SHA-256 verification is performed against the SOURCE for each file.
The experimental fork shares unmodified physical blocks via APFS clonefile.
No full-byte-copy fallback is permitted, and disposition awaits human review.

Usage:
  python3 -B scripts/prepare_learning_experiment.py --source ~/Code/bilqis-mlx/runs/school-mlx-v1
  python3 -B scripts/prepare_learning_experiment.py --source ~/Code/bilqis-mlx/runs/school-mlx-v1 --confirm-clone
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "runs" / "teacher-soup-parity-experiment"
GiB = 1024**3
APFS_PLATFORM_ERROR = "EXPERIMENT_APFS_CLONE_REQUIRES_MACOS"


def digest(path: Path) -> str:
    hash_ = hashlib.sha256()
    with path.open("rb") as reader:
        for chunk in iter(lambda: reader.read(1024*1024), b""):
            hash_.update(chunk)
    return hash_.hexdigest()


def inventory(source: Path) -> tuple[list[tuple[Path, int]], dict]:
    if source.is_symlink() or not source.is_dir():
        raise ValueError("EXPERIMENT_SOURCE_MUST_BE_REAL_DIRECTORY")
    state = json.loads((source/"state.json").read_text())
    pointer = state["school"]["current_student"]
    if (not pointer.get("model_and_native_adamw") or
            not pointer["filename"].startswith("bundles/") or
            Path(pointer["filename"]).parts[:1] != ("bundles",)):
        raise ValueError("EXPERIMENT_SOURCE_NOT_WHOLE_STUDENT")
    checkpoint_file = source/pointer["filename"]/"model-and-own-adamw.safetensors"
    if not checkpoint_file.is_file() or digest(checkpoint_file) != pointer["sha256"]:
        raise ValueError("EXPERIMENT_SOURCE_CHECKPOINT_SHA_DRIFT")
    entries = []
    for parent, directories, files in os.walk(source, followlinks=False):
        root = Path(parent)
        for name in directories + files:
            if (root/name).is_symlink():
                raise ValueError("EXPERIMENT_SOURCE_CONTAINS_SYMLINK")
        for name in files:
            p = root/name
            if not p.is_file():
                raise ValueError("EXPERIMENT_SOURCE_UNSUPPORTED_FILE")
            entries.append((p.relative_to(source), p.stat().st_size))
    return sorted(entries), {"generation": state["generation"],
                             "optimizer_step": pointer["optimizer_step"],
                             "student_sha256": pointer["sha256"],
                             "teacher_events": state["teacher"]["events"],
                             "parameter_geometry": {k:state["config"].get(k)
                               for k in ("layers","width","heads")}}


def trainer_guard():
    observed = subprocess.check_output(["ps","-axo","command="],text=True)
    if any("bilqis_mlx.cli train" in row and
           ("--human-run" in row or "python" in row)
           for row in observed.splitlines()):
        raise ValueError("EXPERIMENT_CLONE_BLOCKED_WHILE_TRAINER_ACTIVE")


@contextmanager
def source_operator_lock(source: Path):
    """Use the trainer's actual flock, not a process-name race check."""
    lock = source / ".grade-a-operator.lock"
    if lock.is_symlink() or not lock.is_file():
        raise ValueError("EXPERIMENT_SOURCE_OPERATOR_LOCK_MISSING")
    fd = os.open(lock, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("EXPERIMENT_SOURCE_TRAINER_LOCK_HELD") from exc
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def clone_copy_on_write(source: Path, destination: Path):
    """Refuse unsupported clonefile, never fall back to an 8 GiB byte copy."""
    if sys.platform != "darwin":
        raise ValueError(APFS_PLATFORM_ERROR)
    subprocess.run(["/bin/cp", "-cR", str(source), str(destination)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _manifest_path(destination: Path) -> Path:
    return destination.with_name(destination.name + ".fork-manifest.json")


def disposition_plan(destination: Path) -> dict:
    """Read-only choice preview. Does not delete either source or fork."""
    destination = destination.expanduser().absolute()
    manifest = _manifest_path(destination)
    if (not destination.is_dir() or destination.is_symlink() or
            not manifest.is_file() or manifest.is_symlink()):
        raise ValueError("EXPERIMENT_FORK_MANIFEST_OR_DESTINATION_MISSING")
    record = json.loads(manifest.read_text())
    if (record.get("schema") != "bilqis.mlx.cow-experiment-fork/v1" or
            record.get("destination") != str(destination) or
            record.get("source_deleted") is not False):
        raise ValueError("EXPERIMENT_FORK_MANIFEST_IDENTITY_DRIFT")
    fork = inventory(destination)[1]
    unchanged = fork == record["source_receipt"]
    return {"disposition": "AWAITING_HUMAN_KEEP_OR_DISCARD_DECISION",
            "fork": str(destination), "source": record["source"],
            "still_at_initial_checkpoint": unchanged,
            "associated_experiment_assets": record.get("associated_experiment_assets", []),
            "initial_student_sha256": record["source_receipt"]["student_sha256"],
            "current_fork_student_sha256": fork["student_sha256"],
            "discard": "Retire the isolated fork only after confirming no unique trial evidence must survive",
            "keep": "Review unique lineages and promote fork explicitly; retire only verified redundant copies, preserve unique original history",
            "source_automatically_deleted": False,
            "fork_automatically_deleted": False}


def execute(source: Path, destination: Path, *, confirm=False, reserve_gib=100) -> dict:
    source = source.expanduser().resolve(strict=True)
    destination = destination.expanduser().absolute()
    if (source == destination or source in destination.parents or
            destination == ROOT or destination.is_symlink() or destination.exists() or
            _manifest_path(destination).exists()):
        raise ValueError("EXPERIMENT_DESTINATION_UNSAFE_OR_EXISTS")
    if ROOT not in destination.parents or ROOT/"runs" not in destination.parents:
        raise ValueError("EXPERIMENT_DESTINATION_MUST_BE_ISOLATED_WORKTREE_RUN")
    records, provenance = inventory(source)
    total = sum(size for _,size in records)
    report = {"source":str(source),"destination":str(destination),
              "files":len(records),"bytes":total,"source_receipt":provenance,
              "cloned":False,"source_deleted":False,
              "copy_mode":"MACOS_APFS_CLONEFILE_COW"}
    if not confirm:
        return report
    if sys.platform != "darwin":
        raise ValueError(APFS_PLATFORM_ERROR)
    trainer_guard()
    with source_operator_lock(source):
        trainer_guard()
        locked_records, locked_provenance = inventory(source)
        if locked_records != records or locked_provenance != provenance:
            raise ValueError("EXPERIMENT_SOURCE_CHANGED_DURING_PREFLIGHT")
        destination.parent.mkdir(parents=True,exist_ok=True)
        free = shutil.disk_usage(destination.parent).free
        if free < reserve_gib*GiB + 600_000_000:
            raise ValueError("EXPERIMENT_CLONE_DISK_HEADROOM_INSUFFICIENT")
        folder = Path(tempfile.mkdtemp(prefix=".learning-clone-",dir=destination.parent))
        staging = folder/"run"
        try:
            clone_copy_on_write(source, staging)
            for rel,size in records:
                copied = staging/rel
                if not copied.is_file() or copied.stat().st_size != size or (
                        digest(copied) != digest(source/rel)):
                    raise ValueError("EXPERIMENT_CLONE_SOURCE_READBACK_MISMATCH:"+str(rel))
            trainer_guard()
            if inventory(source)[1] != provenance:
                raise ValueError("EXPERIMENT_CLONE_SOURCE_CHANGED_DURING_COPY")
            if destination.exists() or destination.is_symlink() or _manifest_path(destination).exists():
                raise ValueError("EXPERIMENT_CLONE_DESTINATION_COLLISION")
            manifest = {"schema":"bilqis.mlx.cow-experiment-fork/v1",
                        "source":str(source), "destination":str(destination),
                        "source_receipt":provenance,
                        "source_state_sha256": digest(source/"state.json"),
                        "files":len(records), "logical_bytes":total,
                        "copy_mode":"MACOS_APFS_CLONEFILE_COW",
                        "decision":"AWAITING_HUMAN_REVIEW", "source_deleted":False}
            staging.rename(destination)
            _manifest_path(destination).write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
            report["cloned"] = True
            report["verified_files"] = len(records)
            report["fork_manifest"] = str(_manifest_path(destination))
        finally:
            # Leave any unexpected partial fork for explicit inspection.
            if not report["cloned"]:
                print("Partial fork, if any, retained at "+str(folder),file=sys.stderr)
            else:
                folder.rmdir()
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--destination",type=Path,default=DESTINATION)
    parser.add_argument("--confirm-clone",action="store_true")
    parser.add_argument("--reserve-gib",type=int,default=100)
    parser.add_argument("--plan-disposition",action="store_true")
    args=parser.parse_args()
    try:
        result=(disposition_plan(args.destination) if args.plan_disposition else
                execute(args.source,args.destination,confirm=args.confirm_clone,
                        reserve_gib=args.reserve_gib))
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError) as exc:
        print("CLONE STOPPED: "+str(exc),file=sys.stderr)
        return 2
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
