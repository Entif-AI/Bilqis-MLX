"""Copy and verify explicit retired code/model trees to an external disk.

There is NO delete/remove/prune operation. The script never walks ~/Code
without the operator naming a specific, narrower source directory. It
preserves directories, files and symlink *identities* without dereferencing
external paths. It hashes every copied file and rechecks the destination;
unsupported special entries cause an error, not a silent omission.

Usage:
  python3 -m bilqis_mlx.backup plan --source PATH [--source PATH ...] --destination /Volumes/DRIVE
  python3 -m bilqis_mlx.backup copy --source PATH [--source PATH ...] --destination /Volumes/DRIVE --confirm-copy --max-gib 400
  python3 -m bilqis_mlx.backup verify --manifest /Volumes/DRIVE/bilqis-mlx-archive/<source-id>/manifest.json

For self-contained Git history when archiving a linked Git worktree, create a
separate Git bundle before eventual retirement. `.git` pointer files alone
cannot recreate Git's shared object database. This tool never claims to have
archived external Git objects it was not given.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat


SCHEMA = "bilqis.external-cold-backup/v1"
CHUNK = 4 * 1024 * 1024


@dataclass(frozen=True)
class Entry:
    path: str
    kind: str
    size_bytes: int = 0
    sha256: str | None = None
    link_target: str | None = None
    link_storage: str = "native"


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _identity(path: Path) -> str:
    h = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]
    return f"{path.name}-{h}"


def safe_source(path: Path) -> Path:
    path = Path(path).expanduser()
    if path.is_symlink() or not path.is_dir():
        raise ValueError("SOURCE_MUST_BE_EXISTING_NONLINK_DIRECTORY")
    location = path.resolve(strict=True)
    home = Path.home().resolve()
    forbidden = {Path("/"), home, home / "Code", home / "Desktop",
                 home / "Documents", home / "Downloads"}
    if location in forbidden or len(location.parts) < 4:
        raise ValueError("BACKUP_REFUSES_BROAD_HOME_OR_CODE_DIRECTORY")
    return location


def _entries(source: Path) -> tuple[Entry, ...]:
    """Enumerate every entry; ignore nothing, including dotfiles and .git."""
    results = []
    for base, dirs, files in os.walk(source, topdown=True, followlinks=False):
        dirs.sort()
        files.sort()
        folder = Path(base)
        for name in list(dirs):
            path = folder / name
            relative = path.relative_to(source).as_posix()
            if path.is_symlink():
                results.append(Entry(relative, "symlink", link_target=os.readlink(path)))
                dirs.remove(name)
            else:
                results.append(Entry(relative, "directory"))
        for name in files:
            path = folder / name
            relative = path.relative_to(source).as_posix()
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                results.append(Entry(relative, "symlink", link_target=os.readlink(path)))
            elif stat.S_ISREG(info.st_mode):
                results.append(Entry(relative, "file", size_bytes=info.st_size))
            else:
                raise ValueError("BACKUP_UNSUPPORTED_SPECIAL_FILE:" + relative)
    return tuple(sorted(results, key=lambda item: item.path))


def plan(sources: list[Path], destination: Path) -> dict:
    if not sources:
        raise ValueError("BACKUP_NO_EXPLICIT_SOURCE")
    distinct = [safe_source(source) for source in sources]
    if len(set(distinct)) != len(distinct):
        raise ValueError("BACKUP_DUPLICATE_SOURCE")
    destination = Path(destination).expanduser()
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError("BACKUP_TARGET_MUST_BE_EXISTING_DIRECTORY")
    dest = destination.resolve(strict=True)
    for source in distinct:
        if dest == source or dest in source.parents or source in dest.parents:
            raise ValueError("BACKUP_SOURCE_DESTINATION_OVERLAP")
    result = []
    for source in distinct:
        entries = _entries(source)
        result.append({"source": str(source), "archive_id": _identity(source),
                       "entries": len(entries),
                       "file_count": sum(e.kind == "file" for e in entries),
                       "symlink_count": sum(e.kind == "symlink" for e in entries),
                       "bytes": sum(e.size_bytes for e in entries),
                       "git_object_warning": (source / ".git").is_file()})
    return {"status": "PLAN_ONLY_NO_FILES_COPIED", "source_trees": result,
            "total_bytes": sum(x["bytes"] for x in result),
            "total_entries": sum(x["entries"] for x in result),
            "destination": str(dest), "local_sources_deleted": False}


def _verify_target(target: Path, entry: Entry) -> None:
    if entry.kind == "file":
        if target.is_symlink() or not target.is_file() or target.stat().st_size != entry.size_bytes:
            raise ValueError("BACKUP_DESTINATION_FILE_MISSING_OR_WRONG_SIZE:"+entry.path)
        if digest_file(target) != entry.sha256:
            raise ValueError("BACKUP_DESTINATION_HASH_MISMATCH:"+entry.path)
    elif entry.kind == "symlink":
        if entry.link_storage == "manifest_only":
            if target.exists() or target.is_symlink() or not isinstance(entry.link_target, str):
                raise ValueError("BACKUP_MANIFEST_ONLY_LINK_COLLISION:"+entry.path)
        elif entry.link_storage == "native":
            if not target.is_symlink() or os.readlink(target) != entry.link_target:
                raise ValueError("BACKUP_DESTINATION_LINK_MISMATCH:"+entry.path)
        else:
            raise ValueError("BACKUP_UNKNOWN_LINK_REPRESENTATION")
    elif entry.kind == "directory":
        if target.is_symlink() or not target.is_dir():
            raise ValueError("BACKUP_DESTINATION_DIRECTORY_MISSING:"+entry.path)
    else:
        raise ValueError("BACKUP_UNKNOWN_ENTRY_KIND")


def _reject_symlink_parents(tree: Path, path: Path) -> None:
    """Never follow a destination-parent link out of an external archive."""
    if tree.is_symlink() or not tree.is_dir():
        raise ValueError("BACKUP_ARCHIVE_TREE_UNSAFE")
    ancestor = path.parent
    while ancestor != tree:
        if ancestor.is_symlink():
            raise ValueError("BACKUP_ARCHIVE_SYMLINK_PARENT:" + str(ancestor))
        if ancestor == ancestor.parent or tree not in ancestor.parents:
            raise ValueError("BACKUP_OUTSIDE_ARCHIVE_TREE")
        ancestor = ancestor.parent


def _copy_one(source: Path, target: Path, entry: Entry) -> Entry:
    if entry.kind == "directory":
        if target.is_symlink() or (target.exists() and not target.is_dir()):
            raise ValueError("BACKUP_DESTINATION_COLLISION:"+entry.path)
        target.mkdir(parents=True, exist_ok=True)
        return entry
    target.parent.mkdir(parents=True, exist_ok=True)
    if entry.kind == "symlink":
        if target.is_symlink():
            _verify_target(target, entry)
        elif target.exists():
            raise ValueError("BACKUP_DESTINATION_COLLISION:"+entry.path)
        else:
            try:
                target.symlink_to(entry.link_target)
            except OSError as error:
                if error.errno not in (errno.EPERM, errno.EOPNOTSUPP, errno.ENOTSUP, errno.EACCES):
                    raise
                # exFAT and some USB media cannot represent POSIX symlinks.
                # The manifest retains the exact path and link target, so a
                # future POSIX restore can reconstruct it losslessly.
                entry = Entry(entry.path, "symlink",
                              link_target=entry.link_target,
                              link_storage="manifest_only")
        _verify_target(target, entry)
        return entry
    if entry.kind != "file":
        raise ValueError("BACKUP_UNSUPPORTED_ENTRY")
    if source.is_symlink() or not source.is_file():
        raise ValueError("BACKUP_SOURCE_CHANGED_TYPE:"+entry.path)
    digest = digest_file(source)
    filled = Entry(entry.path, "file", entry.size_bytes, digest)
    if source.stat().st_size != entry.size_bytes:
        raise ValueError("BACKUP_SOURCE_CHANGED_SIZE:"+entry.path)
    if target.exists() or target.is_symlink():
        _verify_target(target, filled)
        return filled
    # Creation with 'xb' is atomic/exclusive on FAT/exFAT/APFS alike. No hard
    # links are used; an interrupted write never touches the source, and a
    # partially written destination fails readback instead of masquerading as
    # a complete backup.
    created = False
    try:
        with source.open("rb") as reader, target.open("xb") as writer:
            created = True
            shutil.copyfileobj(reader, writer, CHUNK)
            writer.flush()
            os.fsync(writer.fileno())
        # Metadata preservation is best-effort on FAT media. File bytes,
        # layout and source SHA are authoritative for backup correctness.
        try:
            shutil.copystat(source,target,follow_symlinks=False)
        except OSError:
            pass
        _verify_target(target,filled)
        if digest_file(source) != digest:
            raise ValueError("BACKUP_SOURCE_CHANGED_DURING_COPY:"+entry.path)
    except Exception:
        if created:
            target.unlink(missing_ok=True)
        raise
    return filled


def _create_manifest_once(archive: Path, manifest: dict):
    location = archive / "manifest.json"
    if location.is_file():
        previous = json.loads(location.read_text(encoding="utf-8"))
        check = {k:v for k,v in previous.items() if k != "created_utc"}
        if check != {k:v for k,v in manifest.items() if k != "created_utc"}:
            raise ValueError("BACKUP_EXISTING_MANIFEST_CONFLICT")
        return
    created = False
    try:
        with location.open("x",encoding="utf-8") as stream:
            created = True
            json.dump(manifest,stream,sort_keys=True,indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        if created:
            location.unlink(missing_ok=True)
        raise


def copy(sources: list[Path], destination: Path, *, confirm_copy: bool,
         max_gib: float, require_external: bool = True,
         minimum_destination_free_gib: float = 10) -> dict:
    if not confirm_copy:
        raise ValueError("BACKUP_COPY_REQUIRES_EXPLICIT_CONFIRMATION")
    forecast = plan(sources,destination)
    total = forecast["total_bytes"]
    if max_gib < 0 or total > int(max_gib * 1024**3):
        raise ValueError("BACKUP_EXCEEDS_EXPLICIT_OPERATOR_GIB_CAP")
    dest = Path(destination).expanduser().resolve(strict=True)
    if shutil.disk_usage(dest).free < total + int(minimum_destination_free_gib * 1024**3):
        raise ValueError("BACKUP_EXTERNAL_DRIVE_LACKS_SPACE")
    if require_external and any(os.stat(row["source"]).st_dev == os.stat(dest).st_dev
                                for row in forecast["source_trees"]):
        raise ValueError("BACKUP_REQUIRES_SEPARATE_EXTERNAL_VOLUME")
    archives = []
    for row in forecast["source_trees"]:
        source = Path(row["source"])
        archive = dest / "bilqis-mlx-archive" / row["archive_id"]
        if archive.is_symlink():
            raise ValueError("BACKUP_ARCHIVE_ROOT_SYMLINK")
        archive.mkdir(parents=True, exist_ok=True)
        tree = archive / "tree"
        if tree.is_symlink():
            raise ValueError("BACKUP_ARCHIVE_TREE_SYMLINK")
        tree.mkdir(exist_ok=True)
        records = []
        for entry in _entries(source):
            _reject_symlink_parents(tree, tree/entry.path)
            copied = _copy_one(source/entry.path,tree/entry.path,entry)
            records.append(asdict(copied))
        manifest = {"schema": SCHEMA,"source":str(source),
                    "archive_id":row["archive_id"],
                    "created_utc":datetime.now(timezone.utc).isoformat(),
                    "entries":records,"source_entries":len(records),
                    "total_source_bytes":row["bytes"],
                    "external_git_objects_copied":False,
                    "git_object_warning":row["git_object_warning"],
                    "sources_deleted":False}
        _create_manifest_once(archive,manifest)
        verified = verify(archive/"manifest.json")
        archives.append({"manifest":str(archive/"manifest.json"),
                         "verified_entries":verified["verified_entries"],
                         "verified_bytes":verified["verified_bytes"]})
    return {"status":"COPY_VERIFIED_NO_SOURCE_DELETION",
            "archives":archives,"sources_deleted":False}


def verify(manifest_path: Path) -> dict:
    manifest_path = Path(manifest_path).expanduser().resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA or manifest.get("sources_deleted") is not False:
        raise ValueError("BACKUP_MANIFEST_INVALID_SCHEMA")
    tree = manifest_path.parent / "tree"
    entries = [Entry(**x) for x in manifest["entries"]]
    for entry in entries:
        path = Path(entry.path)
        if (path.is_absolute() or path.as_posix() in (".", "..") or
                ".." in path.parts or "\\" in entry.path):
            raise ValueError("BACKUP_UNSAFE_MANIFEST_PATH")
        _reject_symlink_parents(tree,tree/path)
        _verify_target(tree/path,entry)
    if len(entries) != manifest["source_entries"]:
        raise ValueError("BACKUP_ENTRY_COUNT_MISMATCH")
    byte_count = sum(entry.size_bytes for entry in entries)
    if byte_count != manifest["total_source_bytes"]:
        raise ValueError("BACKUP_BYTE_COUNT_MISMATCH")
    return {"status":"EVERY_MANIFEST_ENTRY_VERIFIED", "verified_entries":len(entries),
            "verified_bytes":byte_count,"source":manifest["source"],
            "sources_deleted":False,
            "git_object_warning":manifest["git_object_warning"]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=("plan","copy","verify"))
    p.add_argument("--source",action="append",type=Path,default=[])
    p.add_argument("--destination",type=Path)
    p.add_argument("--manifest",type=Path)
    p.add_argument("--confirm-copy",action="store_true")
    p.add_argument("--max-gib",type=float)
    args = p.parse_args(argv)
    if args.command == "verify":
        if not args.manifest:
            p.error("verify requires --manifest")
        result = verify(args.manifest)
    else:
        if not args.destination or not args.source:
            p.error("plan/copy require explicit --source and --destination")
        if args.command == "plan":
            result = plan(args.source,args.destination)
        else:
            if args.max_gib is None:
                p.error("copy requires an explicit --max-gib budget")
            result = copy(args.source,args.destination,confirm_copy=args.confirm_copy,
                          max_gib=args.max_gib)
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__ == "__main__":
    main()
