"""Isolated source view for the Python-only BAMF readiness predicate."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

from .verification_ledger import fingerprint, full_requested


EXCLUDED = ("apps/mission-control", "docs/evidence/development")
EDITABLE_METADATA = "bilqis_mlx_private.egg-info"
ROOT = Path(__file__).resolve().parents[2]


def _git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "--no-replace-objects", *args], cwd=root)


def _excluded(path: str) -> bool:
    return any(path == directory or path.startswith(directory + "/") for directory in EXCLUDED)


def _entries(root: Path) -> dict[str, tuple[str, str]]:
    entries = {}
    for row in _git(root, "ls-tree", "-r", "-z", "HEAD").split(b"\0"):
        if row:
            header, name = row.split(b"\t", 1)
            mode, kind, oid = header.decode().split()
            path = os.fsdecode(name)
            if _excluded(path):
                continue
            if kind != "blob":
                raise ValueError("unsupported projected Git entry")
            entries[path] = (mode, oid)
    return entries


def _object_id(path: Path, mode: str, algorithm: str) -> str | None:
    if mode == "120000":
        if not path.is_symlink():
            return None
        raw = os.fsencode(os.readlink(path))
        return hashlib.new(algorithm, f"blob {len(raw)}\0".encode() + raw).hexdigest()
    if path.is_symlink() or not path.is_file():
        return None
    info = path.stat()
    if bool(info.st_mode & 0o111) != (mode == "100755"):
        return None
    digest = hashlib.new(algorithm, f"blob {info.st_size}\0".encode())
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_projection(root: Path, source: Path) -> str | None:
    """Accept only the exact archived tree plus editable install metadata."""
    try:
        if source == root or not source.is_dir() or (source / ".git").exists():
            return None
        expected = _entries(root)
        algorithm = _git(root, "rev-parse", "--show-object-format").decode().strip()
        expected_directories = {
            str(parent) for name in expected for parent in Path(name).parents
            if str(parent) != "."
        }
        actual = set()
        directories = set()
        for path in source.rglob("*"):
            name = path.relative_to(source).as_posix()
            if (name == EDITABLE_METADATA or name.startswith(EDITABLE_METADATA + "/")):
                if not path.is_symlink():
                    continue
            if path.is_symlink() or path.is_file():
                actual.add(name)
            elif path.is_dir():
                directories.add(name)
        if actual != expected.keys() or directories != expected_directories:
            return None
        for name, (mode, oid) in expected.items():
            path = source / name
            if not path.resolve().is_relative_to(source):
                return None
            if _object_id(path, mode, algorithm) != oid:
                return None
        return fingerprint("readiness-projection/v1", EXCLUDED, expected)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def prepare(root: Path, destination: Path) -> bool:
    if destination.exists() or destination.is_symlink():
        return False
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
            base = Path(temporary)
            archive = base / "source.tar"
            view = base / "view"
            view.mkdir()
            with archive.open("wb") as stream:
                subprocess.run(
                    ["git", "--no-replace-objects", "archive", "--format=tar", "HEAD",
                     "--", ".", *(f":(exclude){name}" for name in EXCLUDED)],
                    cwd=root, stdout=stream, check=True,
                )
            with tarfile.open(archive) as stream:
                stream.extractall(view, filter="data")
            if validate_projection(root, view) is None:
                return False
            view.rename(destination)
        return True
    except (OSError, ValueError, tarfile.TarError, subprocess.SubprocessError):
        return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    destination = args.output.resolve()
    ready = not full_requested() and prepare(ROOT, destination)
    source = destination if ready else ROOT
    print(f"READINESS_SOURCE {'PROJECTED' if ready else 'FULL'} {source}")
    if environment := os.environ.get("GITHUB_ENV"):
        with Path(environment).open("a", encoding="utf-8") as stream:
            stream.write(f"BILQIS_READINESS_SOURCE={source}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
