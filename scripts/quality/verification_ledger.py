"""Disposable content-addressed verification results shared by local worktrees."""
from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys


def fingerprint(*parts: object) -> str:
    raw = json.dumps(parts, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def full_requested() -> bool:
    if os.environ.get("BILQIS_VERIFICATION_FULL", "").lower() in {"1", "true"}:
        return True
    # A retry must not resurrect evidence superseded by its earlier failure.
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return os.environ.get("GITHUB_RUN_ATTEMPT", "1") != "1"
    return False


def ledger_path(root: Path) -> Path | None:
    override = os.environ.get("BILQIS_VERIFICATION_LEDGER")
    if override:
        return Path(override).resolve()
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return None
    result = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"], cwd=root,
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        return None
    return (root / result.stdout.strip()).resolve() / "verification-ledger.sqlite3"


def source_fingerprint(paths: Sequence[Path]) -> str:
    return fingerprint(sys.implementation.name, sys.version,
                       [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths])


def trusted_input_path() -> Path | None:
    """Only the restore step can establish the hosted input artifact."""
    name = os.environ.get("BILQIS_VERIFICATION_TRUSTED_LEDGER")
    expected = os.environ.get("BILQIS_VERIFICATION_TRUSTED_SHA256")
    if not name or not expected:
        return None
    try:
        path = Path(name).resolve(strict=True)
        if path.stat().st_size > 64 * 1024 * 1024:
            return None
        if hashlib.sha256(path.read_bytes()).hexdigest() == expected:
            return path
    except OSError:
        pass
    return None


class VerificationLedger:
    """A failed lookup or write never changes the verification outcome."""

    def __init__(self, path: Path | None, *, full: bool = False):
        self.full = full
        self.connection = None
        self.reader = None
        self.pending = {}
        self.hits = 0
        self.misses = 0
        if path is not None:
            self._open(path)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            self._open_trusted_reader(path)
        else:
            self.reader = self.connection

    def _open_trusted_reader(self, output: Path | None) -> None:
        trusted = trusted_input_path()
        if trusted is None or (output is not None and trusted == output.resolve()):
            return
        try:
            self.reader = sqlite3.connect(trusted.as_uri() + "?mode=ro", uri=True,
                                          timeout=0.25)
        except sqlite3.Error:
            self.reader = None

    def _open(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if os.environ.get("GITHUB_ACTIONS") != "true":
                self._ensure_local_owner(path)
            self.connection = sqlite3.connect(path, timeout=0.25)
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS receipt_v1 ("
                "scope TEXT NOT NULL, key TEXT NOT NULL, payload TEXT NOT NULL, "
                "digest TEXT NOT NULL, PRIMARY KEY (scope, key))"
            )
            self.connection.commit()
        except (OSError, sqlite3.Error) as error:
            self._unavailable(error)

    @staticmethod
    def _ensure_local_owner(path: Path) -> None:
        # The local cache is a same-account performance facility, not a
        # substitute for independent hosted verification.
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        info = path.stat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)):
            raise PermissionError("untrusted local ledger ownership or permissions")

    def _unavailable(self, error: Exception) -> None:
        print(f"VERIFICATION_LEDGER_UNAVAILABLE {type(error).__name__}", file=sys.stderr)
        if self.connection is not None:
            if self.reader is self.connection:
                self.reader = None
            self.connection.close()
            self.connection = None

    def _read(self, scope: str, key: str):
        if self.full:
            return None
        if (scope, key) in self.pending:
            return self.pending[scope, key]
        if self.reader is None:
            return None
        try:
            row = self.reader.execute(
                "SELECT payload, digest FROM receipt_v1 WHERE scope=? AND key=?",
                (scope, key),
            ).fetchone()
            if row is None or fingerprint(scope, key, row[0]) != row[1]:
                return None
            return json.loads(row[0])
        except (sqlite3.Error, ValueError, TypeError) as error:
            print(f"VERIFICATION_LEDGER_READ_UNAVAILABLE {type(error).__name__}", file=sys.stderr)
            if self.reader is not self.connection:
                self.reader.close()
            self.reader = None
            return None

    def lookup(self, scope: str, key: str, *, validate):
        payload = self._read(scope, key)
        if payload is not None and validate(payload):
            self.hits += 1
            return payload
        self.misses += 1
        return None

    def record(self, scope: str, key: str, payload) -> None:
        self.pending[scope, key] = payload

    def close(self) -> None:
        if self.reader is not None and self.reader is not self.connection:
            self.reader.close()
        self.reader = None
        if self.connection is None:
            return
        try:
            rows = []
            for (scope, key), payload in self.pending.items():
                raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
                rows.append((scope, key, raw, fingerprint(scope, key, raw)))
            self.connection.executemany(
                "INSERT OR REPLACE INTO receipt_v1 VALUES (?, ?, ?, ?)", rows,
            )
            self.connection.commit()
        except (OSError, sqlite3.Error) as error:
            self._unavailable(error)
        finally:
            if self.connection is not None:
                self.connection.close()
                self.connection = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def report(self, scope: str, elapsed: float) -> None:
        print(f"VERIFICATION_LEDGER {scope} hits={self.hits} misses={self.misses} "
              f"elapsed={elapsed:.3f}s", file=sys.stderr)
