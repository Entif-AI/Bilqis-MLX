#!/usr/bin/env python3
"""Plan or explicitly clone a *stopped* saved Bilqis run for parity-size trials.

No source deletion, live trainer invocation, optimizer step, or existing-target
overwrite. SHA-256 verification is performed against the SOURCE for each file.

Usage:
  python3 -B scripts/prepare_learning_experiment.py --source ~/Code/bilqis-mlx/runs/school-mlx-v1
  python3 -B scripts/prepare_learning_experiment.py --source ~/Code/bilqis-mlx/runs/school-mlx-v1 --confirm-clone
"""
from __future__ import annotations

import argparse
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


def execute(source: Path, destination: Path, *, confirm=False, reserve_gib=100) -> dict:
    source = source.expanduser().resolve(strict=True)
    destination = destination.expanduser().absolute()
    if (source == destination or source in destination.parents or
            destination == ROOT or destination.is_symlink() or destination.exists()):
        raise ValueError("EXPERIMENT_DESTINATION_UNSAFE_OR_EXISTS")
    if ROOT not in destination.parents or ROOT/"runs" not in destination.parents:
        raise ValueError("EXPERIMENT_DESTINATION_MUST_BE_ISOLATED_WORKTREE_RUN")
    records, provenance = inventory(source)
    total = sum(size for _,size in records)
    report = {"source":str(source),"destination":str(destination),
              "files":len(records),"bytes":total,"source_receipt":provenance,
              "cloned":False,"source_deleted":False}
    if not confirm:
        return report
    trainer_guard()
    destination.parent.mkdir(parents=True,exist_ok=True)
    free = shutil.disk_usage(destination.parent).free
    if free < total*2 + reserve_gib*GiB:
        raise ValueError("EXPERIMENT_CLONE_DISK_HEADROOM_INSUFFICIENT")
    folder = Path(tempfile.mkdtemp(prefix=".learning-clone-",dir=destination.parent))
    staging = folder/"run"
    try:
        shutil.copytree(source,staging,symlinks=True)
        for rel,size in records:
            copied = staging/rel
            if not copied.is_file() or copied.stat().st_size != size or (
                    digest(copied) != digest(source/rel)):
                raise ValueError("EXPERIMENT_CLONE_SOURCE_READBACK_MISMATCH:"+str(rel))
        trainer_guard()
        if inventory(source)[1] != provenance:
            raise ValueError("EXPERIMENT_CLONE_SOURCE_CHANGED_DURING_COPY")
        if destination.exists() or destination.is_symlink():
            raise ValueError("EXPERIMENT_CLONE_DESTINATION_COLLISION")
        staging.rename(destination)
        report["cloned"] = True
        report["verified_files"] = len(records)
    finally:
        # On an unexpected failure, retain the sole, self-owned staging
        # directory for explicit inspection rather than deleting evidence.
        if not report["cloned"]:
            print("Partial clone, if any, retained at "+str(folder),file=sys.stderr)
        else:
            folder.rmdir()
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--destination",type=Path,default=DESTINATION)
    parser.add_argument("--confirm-clone",action="store_true")
    parser.add_argument("--reserve-gib",type=int,default=100)
    args=parser.parse_args()
    try:
        result=execute(args.source,args.destination,confirm=args.confirm_clone,
                       reserve_gib=args.reserve_gib)
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError) as exc:
        print("CLONE STOPPED: "+str(exc),file=sys.stderr)
        return 2
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
