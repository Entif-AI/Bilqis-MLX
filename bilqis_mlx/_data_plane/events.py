"""Append-only event ledger indexing owner."""
from __future__ import annotations
from pathlib import Path
from .contracts import DataPlaneError, _error, _read_event_tail

class DataPlaneEventMixin:
    def sync_event_ledger(self, run_dir: Path) -> dict:
        """Index only the unseen append-only JSONL tail for one run."""
        root = Path(run_dir).resolve(strict=True)
        key = str(root)
        ledger = root / "events.jsonl"
        if ledger.is_symlink():
            raise ValueError(_error(DataPlaneError.EVENT_LEDGER_UNSAFE, ledger))
        if not ledger.exists():
            with self.transaction():
                self._db.execute("DELETE FROM event_index WHERE run_dir=?", (key,))
                self._db.execute("DELETE FROM event_ledgers WHERE run_dir=?", (key,))
            return {"run_dir": key, "indexed_bytes": 0, "scanned_bytes": 0,
                    "indexed_events": 0, "rebuilt": False}
        if not ledger.is_file():
            raise ValueError(_error(DataPlaneError.EVENT_LEDGER_UNSAFE, ledger))
        stat = ledger.stat()
        with self._lock:
            prior = self._db.execute(
                "SELECT st_dev,st_ino,indexed_bytes,mtime_ns,ctime_ns "
                "FROM event_ledgers WHERE run_dir=?", (key,)).fetchone()
        rebuild = (
            prior is None or prior[0] != stat.st_dev or prior[1] != stat.st_ino or
            prior[2] > stat.st_size or
            (prior[2] == stat.st_size and
             (prior[3] != stat.st_mtime_ns or prior[4] != stat.st_ctime_ns))
        )
        start = 0 if rebuild else prior[2]
        if start == stat.st_size and not rebuild:
            with self._lock:
                count = self._db.execute(
                    "SELECT COUNT(*) FROM event_index WHERE run_dir=?", (key,)
                ).fetchone()[0]
            return {"run_dir": key, "indexed_bytes": start, "scanned_bytes": 0,
                    "indexed_events": count, "rebuilt": False}

        observed, end = _read_event_tail(ledger, start)

        fresh = ledger.stat()
        with self.transaction():
            if rebuild:
                self._db.execute("DELETE FROM event_index WHERE run_dir=?", (key,))
            for event_id, digest in observed:
                row = self._db.execute(
                    "SELECT payload_sha256,occurrences,conflicted FROM event_index "
                    "WHERE run_dir=? AND event_id=?", (key, event_id)).fetchone()
                if row is None:
                    self._db.execute(
                        "INSERT INTO event_index(run_dir,event_id,payload_sha256,"
                        "occurrences,conflicted) VALUES(?,?,?,?,?)",
                        (key, event_id, digest, 1, False))
                else:
                    conflicted = bool(row[2]) or row[0] != digest
                    self._db.execute(
                        "UPDATE event_index SET occurrences=?,conflicted=? "
                        "WHERE run_dir=? AND event_id=?",
                        (row[1] + 1, conflicted, key, event_id))
            self._db.execute(
                "INSERT OR REPLACE INTO event_ledgers("
                "run_dir,st_dev,st_ino,indexed_bytes,mtime_ns,ctime_ns"
                ") VALUES(?,?,?,?,?,?)",
                (key, fresh.st_dev, fresh.st_ino, end,
                 fresh.st_mtime_ns, fresh.st_ctime_ns))
            count = self._db.execute(
                "SELECT COUNT(*) FROM event_index WHERE run_dir=?", (key,)
            ).fetchone()[0]
        return {"run_dir": key, "indexed_bytes": end,
                "scanned_bytes": end - start, "indexed_events": count,
                "rebuilt": rebuild}

    def event_observations(self, run_dir: Path, event_ids) -> dict:
        self.sync_event_ledger(run_dir)
        key = str(Path(run_dir).resolve(strict=True))
        result = {}
        with self._lock:
            for event_id in event_ids:
                row = self._db.execute(
                    "SELECT payload_sha256,occurrences,conflicted FROM event_index "
                    "WHERE run_dir=? AND event_id=?", (key, event_id)).fetchone()
                if row is not None:
                    result[event_id] = (row[0], row[1], bool(row[2]))
        return result

