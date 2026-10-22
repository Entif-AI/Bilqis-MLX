"""Shared workstation data plane for immutable state and integrity cache."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
import zlib
from contextlib import contextmanager
from enum import Enum

SCHEMA_VERSION = 1
SQLITE_BUSY_TIMEOUT_MS = 30_000
SQLITE_MMAP_BYTES = 256 * 1024 * 1024
SQLITE_CACHE_KIB = 64 * 1024
HASH_CHUNK_BYTES = 4 * 1024 * 1024
SHA256_HEX_LENGTH = hashlib.sha256().digest_size * 2
_CONNECTIONS: dict[str, "DataPlane"] = dict()
_CONNECTIONS_LOCK = threading.Lock()


class DataPlaneError(str, Enum):
    SCHEMA_UNSUPPORTED = "BILQIS_DATA_PLANE_SCHEMA_UNSUPPORTED"
    OBJECT_DIGEST_INVALID = "BILQIS_DATA_PLANE_OBJECT_DIGEST_INVALID"
    OBJECT_MISSING = "BILQIS_DATA_PLANE_OBJECT_MISSING"
    OBJECT_CORRUPTED = "BILQIS_DATA_PLANE_OBJECT_CORRUPTED"
    NODE_DIGEST_INVALID = "BILQIS_DATA_PLANE_NODE_DIGEST_INVALID"
    NODE_MISSING = "BILQIS_DATA_PLANE_NODE_MISSING"
    NODE_CORRUPTED = "BILQIS_DATA_PLANE_NODE_CORRUPTED"
    EXPECTED_DIGEST_INVALID = "BILQIS_DATA_PLANE_EXPECTED_DIGEST_INVALID"
    OPERATOR_LOCK_UNSAFE = "DATA_PLANE_OPERATOR_LOCK_UNSAFE"
    HUMAN_TRAINING_ACTIVE = "DATA_PLANE_WARM_HUMAN_TRAINING_ACTIVE"
    CUSTODY_ARTIFACT_MISSING = "DATA_PLANE_WARM_CUSTODY_ARTIFACT_MISSING"
    CUSTODY_DIGEST_DRIFT = "DATA_PLANE_WARM_CUSTODY_DIGEST_DRIFT"


def _error(code: DataPlaneError, detail=None) -> str:
    return code.value if detail is None else code.value + ":" + str(detail)


def default_path() -> Path:
    configured = os.environ.get("BILQIS_DATA_PLANE", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    home = Path.home()
    if sys.platform == "darwin":
        root = home / "Library" / "Application Support" / "Bilqis-MLX"
    elif os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")) / "Bilqis-MLX"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share")) / "bilqis-mlx"
    return root / "data-plane.sqlite3"


class DataPlane:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(
            self.path, timeout=30.0, isolation_level=None, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        self._db.execute("PRAGMA temp_store=MEMORY")
        self._db.execute(f"PRAGMA mmap_size={SQLITE_MMAP_BYTES}")
        self._db.execute(f"PRAGMA cache_size=-{SQLITE_CACHE_KIB}")
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS meta(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS objects(
            sha256 TEXT PRIMARY KEY,
            payload BLOB NOT NULL,
            raw_bytes INTEGER NOT NULL
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS nodes(
            sha256 TEXT PRIMARY KEY,
            payload BLOB NOT NULL,
            generation INTEGER NOT NULL,
            parent_sha256 TEXT
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS verified_files(
            path TEXT NOT NULL,
            expected_sha256 TEXT NOT NULL,
            st_dev INTEGER NOT NULL,
            st_ino INTEGER NOT NULL,
            size_bytes INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            ctime_ns INTEGER NOT NULL,
            verified_ns INTEGER NOT NULL,
            PRIMARY KEY(path, expected_sha256)
        ) WITHOUT ROWID;
        """)
        row = self._db.execute(
            "SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if row is None:
            self._db.execute(
                "INSERT INTO meta(key,value) VALUES('schema_version',?)",
                (str(SCHEMA_VERSION),))
        elif int(row[0]) != SCHEMA_VERSION:
            raise ValueError(DataPlaneError.SCHEMA_UNSUPPORTED.value)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    @contextmanager
    def transaction(self):
        """One durable multi-object commit; nested callers share this connection."""
        with self._lock:
            if self._db.in_transaction:
                yield self
                return
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield self
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            else:
                self._db.execute("COMMIT")

    def put_object(self, digest: str, raw: bytes) -> None:
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(DataPlaneError.OBJECT_DIGEST_INVALID.value)
        payload = zlib.compress(raw, level=6)
        with self._lock:
            self._db.execute(
                "INSERT OR IGNORE INTO objects(sha256,payload,raw_bytes) VALUES(?,?,?)",
                (digest, payload, len(raw)))

    def get_object(self, digest: str) -> bytes:
        with self._lock:
            row = self._db.execute(
                "SELECT payload,raw_bytes FROM objects WHERE sha256=?", (digest,)
            ).fetchone()
        if row is None:
            raise ValueError(_error(DataPlaneError.OBJECT_MISSING, digest))
        raw = zlib.decompress(row[0])
        if len(raw) != row[1] or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(_error(DataPlaneError.OBJECT_CORRUPTED, digest))
        return raw

    def put_node(self, digest: str, raw: bytes, generation: int,
                 parent_sha256: str | None) -> None:
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(DataPlaneError.NODE_DIGEST_INVALID.value)
        with self._lock:
            self._db.execute(
                "INSERT OR IGNORE INTO nodes(sha256,payload,generation,parent_sha256) "
                "VALUES(?,?,?,?)",
                (digest, raw, generation, parent_sha256))

    def get_node(self, digest: str) -> bytes:
        with self._lock:
            row = self._db.execute(
                "SELECT payload FROM nodes WHERE sha256=?", (digest,)).fetchone()
        if row is None:
            raise ValueError(_error(DataPlaneError.NODE_MISSING, digest))
        raw = row[0]
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(_error(DataPlaneError.NODE_CORRUPTED, digest))
        return raw

    @staticmethod
    def _stat_identity(path: Path) -> tuple[int, int, int, int, int]:
        st = path.stat()
        return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)

    def verified_file(self, path: Path, expected_sha256: str) -> bool:
        path = Path(path).resolve(strict=True)
        identity = self._stat_identity(path)
        with self._lock:
            row = self._db.execute(
                "SELECT st_dev,st_ino,size_bytes,mtime_ns,ctime_ns "
                "FROM verified_files WHERE path=? AND expected_sha256=?",
                (str(path), expected_sha256)).fetchone()
        return row == identity

    def remember_verified_file(self, path: Path, expected_sha256: str) -> None:
        path = Path(path).resolve(strict=True)
        dev, ino, size, mtime, ctime = self._stat_identity(path)
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO verified_files("
                "path,expected_sha256,st_dev,st_ino,size_bytes,mtime_ns,ctime_ns,verified_ns"
                ") VALUES(?,?,?,?,?,?,?,?)",
                (str(path), expected_sha256, dev, ino, size, mtime, ctime,
                 time.time_ns()))

    def stats(self) -> dict:
        with self._lock:
            objects = self._db.execute(
                "SELECT COUNT(*),COALESCE(SUM(length(payload)),0),COALESCE(SUM(raw_bytes),0) "
                "FROM objects").fetchone()
            nodes = self._db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            verified = self._db.execute(
                "SELECT COUNT(*) FROM verified_files").fetchone()[0]
        return {
            "path": str(self.path), "objects": objects[0],
            "compressed_object_bytes": objects[1], "raw_object_bytes": objects[2],
            "nodes": nodes, "verified_files": verified,
        }


def data_plane() -> DataPlane:
    path = str(default_path())
    with _CONNECTIONS_LOCK:
        plane = _CONNECTIONS.get(path)
        if plane is None:
            plane = DataPlane(Path(path))
            _CONNECTIONS[path] = plane
        return plane


def close_data_planes() -> None:
    with _CONNECTIONS_LOCK:
        values = list(_CONNECTIONS.values())
        _CONNECTIONS.clear()
    for plane in values:
        plane.close()


def _digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(HASH_CHUNK_BYTES):
            h.update(chunk)
    return h.hexdigest()


def verify_file_digest(path: Path, expected_sha256: str, *, deep: bool = False) -> bool:
    """Verify immutable file content, reusing a workstation-local stat-bound proof."""
    if not isinstance(expected_sha256, str) or len(expected_sha256) != SHA256_HEX_LENGTH:
        raise ValueError(DataPlaneError.EXPECTED_DIGEST_INVALID.value)
    plane = data_plane()
    path = Path(path)
    if not deep and plane.verified_file(path, expected_sha256):
        return True
    actual = _digest_file(path)
    if actual != expected_sha256:
        return False
    plane.remember_verified_file(path, expected_sha256)
    return True


def referenced_custody_files(run_dir: Path, receipt: dict) -> tuple[tuple[Path, str], ...]:
    """Resolve immutable bundle/soup payloads named by one logical school receipt."""
    root = Path(run_dir).resolve(strict=True)
    found: dict[str, tuple[Path, str]] = {}

    def visit(value) -> None:
        if isinstance(value, dict):
            filename = value.get("filename")
            digest = value.get("sha256")
            if isinstance(filename, str) and isinstance(digest, str) and len(digest) == SHA256_HEX_LENGTH:
                relative = Path(filename)
                if relative.parts and relative.parts[0] == "bundles":
                    target = root / relative / "model-and-own-adamw.safetensors"
                    found[str(target)] = (target, digest)
                elif relative.parts and relative.parts[0] == "soups":
                    target = root / relative
                    found[str(target)] = (target, digest)
            for member in value.values():
                visit(member)
        elif isinstance(value, (list, tuple)):
            for member in value:
                visit(member)

    visit(receipt)
    return tuple(found[key] for key in sorted(found))


def main(argv=None) -> int:
    """Inspect or prewarm the shared workstation data plane."""
    import argparse
    import fcntl
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "warm-custody"))
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


if __name__ == "__main__":
    raise SystemExit(main())
