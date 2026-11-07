"""Crash reconciliation for accepted C09 append/commit transactions."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from bilqis_mlx.data_plane import data_plane

from .accepted_correction_records import _canonical, records_from_bytes, validate_record
from .accepted_correction_storage import (
    clear_transaction, commit_history_and_clear, committed_history, history_state,
    ledger_path, read_transaction,
)
from .atlas_revalidation_common import _invalid


def read_records_unlocked(
    run_dir: Path, manifest_sha256: str,
) -> tuple[dict, ...]:
    path = ledger_path(run_dir)
    if not path.exists():
        return ()
    if path.is_symlink() or not path.is_file():
        _invalid("BAMF_C09_CORRECTION_LEDGER_UNSAFE")
    try:
        raw = path.read_bytes()
    except OSError:
        _invalid("BAMF_C09_CORRECTION_LEDGER_INVALID")
    return records_from_bytes(raw, manifest_sha256)


def _same_history_state(committed: dict | None, state: dict) -> bool:
    return (committed is not None
            and committed["event_ids"] == state["event_ids"]
            and committed["records_sha256"] == state["records_sha256"])


def recover_transaction(run_dir: Path, manifest_sha256: str) -> None:
    transaction = read_transaction(run_dir, manifest_sha256)
    if transaction is None:
        return
    record = validate_record(transaction["record"], manifest_sha256)
    path = ledger_path(run_dir)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        _invalid("BAMF_C09_CORRECTION_LEDGER_UNSAFE")
    try:
        raw = path.read_bytes() if path.exists() else b""
    except OSError:
        _invalid("BAMF_C09_CORRECTION_LEDGER_INVALID")
    prior_size = transaction["prior_file_size"]
    if len(raw) < prior_size:
        _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")
    prefix = raw[:prior_size]
    if hashlib.sha256(prefix).hexdigest() != transaction["prior_file_sha256"]:
        _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")
    prior = records_from_bytes(prefix, manifest_sha256)
    prior_state = history_state(prior)
    expected_prior = {
        "event_ids": transaction["prior_event_ids"],
        "records_sha256": transaction["prior_records_sha256"],
    }
    target = (*prior, record)
    target_state = history_state(target)
    expected_target = {
        "event_ids": transaction["target_event_ids"],
        "records_sha256": transaction["target_records_sha256"],
    }
    if prior_state != expected_prior or target_state != expected_target:
        _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")
    committed = committed_history(run_dir, manifest_sha256)
    committed_is_prior = (
        committed is None and not prior
    ) or _same_history_state(committed, prior_state)
    committed_is_target = _same_history_state(committed, target_state)
    suffix = raw[prior_size:]
    record_line = _canonical(record) + b"\n"
    if not suffix:
        if not committed_is_prior:
            _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")
        clear_transaction(run_dir, manifest_sha256)
        return
    if suffix.startswith(record_line):
        if not (committed_is_prior or committed_is_target):
            _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")
        full = records_from_bytes(raw, manifest_sha256)
        if history_state(full) != target_state:
            _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")
        data_plane().sync_event_ledger(run_dir)
        commit_history_and_clear(run_dir, manifest_sha256, full)
        return
    if record_line.startswith(suffix):
        if not committed_is_prior:
            _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")
        descriptor = os.open(path, os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            os.ftruncate(descriptor, prior_size)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        data_plane().sync_event_ledger(run_dir)
        clear_transaction(run_dir, manifest_sha256)
        return
    _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")


__all__ = ("read_records_unlocked", "recover_transaction")
