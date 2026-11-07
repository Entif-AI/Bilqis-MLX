"""Durable lock and data-plane commitment state for accepted C09 history."""
from __future__ import annotations

import contextlib
from enum import Enum
import fcntl
import hashlib
import json
import os
from pathlib import Path
from threading import RLock

from bilqis_mlx.data_plane import data_plane

from .accepted_correction_records import _canonical
from .atlas_revalidation_common import _invalid


HISTORY_COMMITMENT_SCHEMA = "bilqis.c09.accepted-history/v2"
HISTORY_TRANSACTION_SCHEMA = "bilqis.c09.accepted-history-transaction/v1"
_PROCESS_LEDGER_LOCK = RLock()


class AcceptedCorrectionStorageError(str, Enum):
    SHORT_WRITE = "short write"


def history_state(records: tuple[dict, ...]) -> dict:
    return {
        "event_ids": [record["event_id"] for record in records],
        "records_sha256": hashlib.sha256(_canonical(records)).hexdigest(),
    }


def _history_reference(run_dir: Path, manifest_sha256: str) -> str:
    return hashlib.sha256(_canonical({
        "schema_version": HISTORY_COMMITMENT_SCHEMA,
        "run_dir": str(Path(run_dir).resolve()),
        "accepted_manifest_sha256": manifest_sha256,
    })).hexdigest()


def _transaction_reference(run_dir: Path, manifest_sha256: str) -> str:
    return hashlib.sha256(_canonical({
        "schema_version": HISTORY_TRANSACTION_SCHEMA,
        "run_dir": str(Path(run_dir).resolve()),
        "accepted_manifest_sha256": manifest_sha256,
    })).hexdigest()


def commit_history(
    run_dir: Path, manifest_sha256: str, records: tuple[dict, ...],
) -> None:
    data_plane().put_object_reference(
        _history_reference(run_dir, manifest_sha256),
        _canonical({
            "schema_version": HISTORY_COMMITMENT_SCHEMA,
            "run_dir": str(Path(run_dir).resolve()),
            "accepted_manifest_sha256": manifest_sha256,
            **history_state(records),
        }),
    )


def committed_history(run_dir: Path, manifest_sha256: str) -> dict | None:
    resolved = data_plane().get_object_reference(
        _history_reference(run_dir, manifest_sha256))
    if resolved is None:
        return None
    _digest, raw = resolved
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")
    if (not isinstance(record, dict)
            or record.get("schema_version") != HISTORY_COMMITMENT_SCHEMA
            or record.get("run_dir") != str(Path(run_dir).resolve())
            or record.get("accepted_manifest_sha256") != manifest_sha256
            or not isinstance(record.get("event_ids"), list)
            or not all(isinstance(item, str) and item for item in record["event_ids"])
            or not isinstance(record.get("records_sha256"), str)):
        _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")
    return record


def verify_committed_history(
    run_dir: Path, manifest_sha256: str, records: tuple[dict, ...],
) -> None:
    committed = committed_history(run_dir, manifest_sha256)
    if committed is None:
        return
    state = history_state(records)
    if (committed["event_ids"] != state["event_ids"]
            or committed["records_sha256"] != state["records_sha256"]):
        _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")


def ledger_path(run_dir: Path) -> Path:
    return Path(run_dir) / "events.jsonl"


@contextlib.contextmanager
def ledger_lock(run_dir: Path):
    root = Path(run_dir)
    if root.is_symlink() or not root.is_dir():
        _invalid("BAMF_C09_CORRECTION_LEDGER_UNSAFE")
    path = root / ".c09-events.lock"
    if path.is_symlink():
        _invalid("BAMF_C09_CORRECTION_LEDGER_UNSAFE")
    with _PROCESS_LEDGER_LOCK:
        descriptor = os.open(
            path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


def write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise OSError(AcceptedCorrectionStorageError.SHORT_WRITE.value)
        offset += written


def write_transaction(run_dir: Path, manifest_sha256: str, payload: dict) -> None:
    data_plane().put_object_reference(
        _transaction_reference(run_dir, manifest_sha256), _canonical(payload))


def read_transaction(run_dir: Path, manifest_sha256: str) -> dict | None:
    resolved = data_plane().get_object_reference(
        _transaction_reference(run_dir, manifest_sha256))
    if resolved is None:
        return None
    _digest, raw = resolved
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _invalid("BAMF_C09_CORRECTION_LEDGER_INVALID")
    if (not isinstance(payload, dict)
            or payload.get("schema_version") != HISTORY_TRANSACTION_SCHEMA
            or payload.get("run_dir") != str(Path(run_dir).resolve())
            or payload.get("accepted_manifest_sha256") != manifest_sha256
            or payload.get("state") not in {"IDLE", "PREPARED"}):
        _invalid("BAMF_C09_CORRECTION_LEDGER_INVALID")
    if payload["state"] == "IDLE":
        return None
    if (not isinstance(payload.get("record"), dict)
            or type(payload.get("prior_file_size")) is not int
            or payload["prior_file_size"] < 0
            or not isinstance(payload.get("prior_file_sha256"), str)
            or not isinstance(payload.get("prior_event_ids"), list)
            or not isinstance(payload.get("prior_records_sha256"), str)
            or not isinstance(payload.get("target_event_ids"), list)
            or not isinstance(payload.get("target_records_sha256"), str)):
        _invalid("BAMF_C09_CORRECTION_LEDGER_INVALID")
    return payload


def idle_transaction(run_dir: Path, manifest_sha256: str) -> dict:
    return {
        "schema_version": HISTORY_TRANSACTION_SCHEMA, "state": "IDLE",
        "run_dir": str(Path(run_dir).resolve()),
        "accepted_manifest_sha256": manifest_sha256,
    }


def clear_transaction(run_dir: Path, manifest_sha256: str) -> None:
    write_transaction(run_dir, manifest_sha256, idle_transaction(run_dir, manifest_sha256))


def commit_history_and_clear(
    run_dir: Path, manifest_sha256: str, records: tuple[dict, ...],
) -> None:
    plane = data_plane()
    with plane.transaction():
        commit_history(run_dir, manifest_sha256, records)
        plane.put_object_reference(
            _transaction_reference(run_dir, manifest_sha256),
            _canonical(idle_transaction(run_dir, manifest_sha256)),
        )


__all__ = (
    "HISTORY_COMMITMENT_SCHEMA", "HISTORY_TRANSACTION_SCHEMA", "clear_transaction",
    "commit_history", "commit_history_and_clear", "committed_history", "history_state",
    "idle_transaction", "ledger_lock", "ledger_path", "read_transaction",
    "verify_committed_history", "write_all", "write_transaction",
)
