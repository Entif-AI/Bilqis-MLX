"""Read-only rejection projection over a content-verified journal prefix."""
from hashlib import sha256
import os
from pathlib import Path
from typing import NamedTuple

from bilqis_mlx._data_plane.contracts import HASH_CHUNK_BYTES
from bilqis_mlx.errors import BilqisError

from ..native_contracts import invalid
from ..native_rejections import project_rejection_rows, read_rejection_rows


LEDGER_CHANGED = "CONTROL_PLANE_NATIVE_EVENT_LEDGER_CHANGED_DURING_READ"


class LedgerIdentity(NamedTuple):
    device: int
    inode: int
    size: int
    modified_ns: int
    changed_ns: int


def _identity(stat):
    return LedgerIdentity(stat.st_dev, stat.st_ino, stat.st_size,
                          stat.st_mtime_ns, stat.st_ctime_ns)


def _hash_prefix(stream, size):
    digest = sha256()
    while size:
        block = stream.read(min(size, HASH_CHUNK_BYTES))
        if not block:
            invalid(LEDGER_CHANGED)
        digest.update(block)
        size -= len(block)
    return digest


def _hashed_lines(stream, size, digest):
    while stream.tell() < size:
        raw = stream.readline(size - stream.tell())
        if not raw:
            invalid(LEDGER_CHANGED)
        digest.update(raw)
        yield raw


class RejectionLedgerCache:
    """Reuse signed rows only after proving their journal bytes have not changed.

    The observer is a different process from the append writer. File growth
    alone does not authenticate the old prefix; verify it before skipping JSON
    decoding or signature checks. Legacy backing objects are never memoized.
    """

    def __init__(self):
        self._reset()

    def _reset(self):
        self.identity = self.digest = self.history = None
        self.rows = ()
        self.verified = {}

    def __call__(self, run_dir: Path, history):
        ledger = Path(run_dir) / "events.jsonl"
        if not ledger.exists() and not ledger.is_symlink():
            self._reset()
            return (), ()
        if ledger.is_symlink() or not ledger.is_file():
            invalid("CONTROL_PLANE_NATIVE_EVENT_LEDGER_INVALID")
        before = _identity(ledger.stat())
        try:
            with ledger.open("rb") as stream:
                if _identity(os.fstat(stream.fileno())) != before:
                    invalid(LEDGER_CHANGED)
                rows, digest, reused = self._read(stream, before)
            verified = dict(self.verified) if reused and self.history is history else {}
            material = project_rejection_rows(rows, history, verified_portable=verified)
        except BilqisError:
            self._require_unchanged(ledger, before)
            raise
        except FileNotFoundError:
            invalid(LEDGER_CHANGED)
        self._require_unchanged(ledger, before)
        self.identity, self.digest, self.rows = before, digest, rows
        self.history, self.verified = history, verified
        return material

    def _read(self, stream, before):
        if before == self.identity:
            return self.rows, self.digest, True
        size = before.size
        if self.identity is not None and size >= self.identity.size:
            prefix = _hash_prefix(stream, self.identity.size)
            if prefix.digest() == self.digest:
                rows = tuple(read_rejection_rows(_hashed_lines(stream, size, prefix)))
                return (*self.rows, *rows), prefix.digest(), True
        stream.seek(0)
        digest = sha256()
        rows = tuple(read_rejection_rows(_hashed_lines(stream, size, digest)))
        return rows, digest.digest(), False

    @staticmethod
    def _require_unchanged(ledger, before):
        try:
            if not ledger.is_symlink() and _identity(ledger.stat()) == before:
                return
        except FileNotFoundError:
            pass
        invalid(LEDGER_CHANGED)
