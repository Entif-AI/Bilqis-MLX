"""Durable codec and persistence for accepted-generation C09 evidence."""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
from threading import RLock

from bilqis_mlx.data_plane import data_plane
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef

from .atlas_revalidation_common import _invalid
from .atlas_revalidation_evidence import (
    CorrectionEvent, RevalidatedArtifact, RevalidationFrontier,
)
from .atlas_source_authority import SourceAuthorityRegistry
from .accepted_stale_replay_ledger import (
    DERIVED_CLAIM_EVENT, PROCESS_FAULT_EVENT, REMEDIATION_EVENT,
)
from bilqis_mlx.runtime.capability_support_journal import (
    _event_record, event_from_record,
)


CORRECTION_EVENT = "BAMF_C09_CORRECTION"
REVALIDATION_EVENT = "BAMF_C09_REVALIDATION"
HISTORY_COMMITMENT_SCHEMA = "bilqis.c09.accepted-history/v2"
HISTORY_TRANSACTION_SCHEMA = "bilqis.c09.accepted-history-transaction/v1"
_PROCESS_LEDGER_LOCK = RLock()


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def _history_reference(run_dir: Path, manifest_sha256: str) -> str:
    return hashlib.sha256(_canonical({
        "schema_version": HISTORY_COMMITMENT_SCHEMA,
        "run_dir": str(Path(run_dir).resolve()),
        "accepted_manifest_sha256": manifest_sha256,
    })).hexdigest()


def _history_commitment(
    run_dir: Path, manifest_sha256: str, records: tuple[dict, ...],
) -> bytes:
    state = _history_state(records)
    return _canonical({
        "schema_version": HISTORY_COMMITMENT_SCHEMA,
        "run_dir": str(Path(run_dir).resolve()),
        "accepted_manifest_sha256": manifest_sha256,
        **state,
    })


def _history_state(records: tuple[dict, ...]) -> dict:
    return {
        "event_ids": [record["event_id"] for record in records],
        "records_sha256": hashlib.sha256(_canonical(records)).hexdigest(),
    }


def _commit_history(
    run_dir: Path, manifest_sha256: str, records: tuple[dict, ...],
) -> None:
    data_plane().put_object_reference(
        _history_reference(run_dir, manifest_sha256),
        _history_commitment(run_dir, manifest_sha256, records),
    )


def _committed_history(run_dir: Path, manifest_sha256: str) -> dict | None:
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
            or not all(isinstance(item, str) and item
                       for item in record["event_ids"])
            or not isinstance(record.get("records_sha256"), str)):
        _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")
    return record


def _verify_committed_history(
    run_dir: Path, manifest_sha256: str, records: tuple[dict, ...],
) -> None:
    committed = _committed_history(run_dir, manifest_sha256)
    if committed is None:
        return
    state = _history_state(records)
    if (committed["event_ids"] != state["event_ids"]
            or committed["records_sha256"] != state["records_sha256"]):
        _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")


def _ledger_path(run_dir: Path) -> Path:
    return Path(run_dir) / "events.jsonl"


def _transaction_reference(run_dir: Path, manifest_sha256: str) -> str:
    return hashlib.sha256(_canonical({
        "schema_version": HISTORY_TRANSACTION_SCHEMA,
        "run_dir": str(Path(run_dir).resolve()),
        "accepted_manifest_sha256": manifest_sha256,
    })).hexdigest()


@contextlib.contextmanager
def _ledger_lock(run_dir: Path):
    root = Path(run_dir)
    if root.is_symlink() or not root.is_dir():
        _invalid("BAMF_C09_CORRECTION_LEDGER_UNSAFE")
    path = root / ".c09-events.lock"
    if path.is_symlink():
        _invalid("BAMF_C09_CORRECTION_LEDGER_UNSAFE")
    with _PROCESS_LEDGER_LOCK:
        descriptor = os.open(
            path,
            os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise OSError("short write")
        offset += written


def _write_transaction(run_dir: Path, manifest_sha256: str, payload: dict) -> None:
    data_plane().put_object_reference(
        _transaction_reference(run_dir, manifest_sha256),
        _canonical(payload),
    )


def _read_transaction(run_dir: Path, manifest_sha256: str) -> dict | None:
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


def _idle_transaction(run_dir: Path, manifest_sha256: str) -> dict:
    return {
        "schema_version": HISTORY_TRANSACTION_SCHEMA,
        "state": "IDLE",
        "run_dir": str(Path(run_dir).resolve()),
        "accepted_manifest_sha256": manifest_sha256,
    }


def _clear_transaction(run_dir: Path, manifest_sha256: str) -> None:
    _write_transaction(
        run_dir, manifest_sha256,
        _idle_transaction(run_dir, manifest_sha256),
    )


def _commit_history_and_clear(
    run_dir: Path, manifest_sha256: str, records: tuple[dict, ...],
) -> None:
    plane = data_plane()
    with plane.transaction():
        _commit_history(run_dir, manifest_sha256, records)
        plane.put_object_reference(
            _transaction_reference(run_dir, manifest_sha256),
            _canonical(_idle_transaction(run_dir, manifest_sha256)),
        )


def correction_record(manifest_sha256: str, event: CorrectionEvent) -> dict:
    body = {
        "event": CORRECTION_EVENT,
        "accepted_manifest_sha256": manifest_sha256,
        "correction": _event_record(event),
    }
    return {"event_id": hashlib.sha256(_canonical(body)).hexdigest(), **body}


def _revalidation_payload(frontier: RevalidationFrontier) -> list[dict]:
    return [
        {
            "artifact_id": item.artifact_id,
            "immediate_dependencies": [
                {"kind": ref.kind.value, "key": ref.key}
                for ref in item.immediate_dependencies
            ],
            "content_digest": item.content_digest,
            "eligible": item.eligible,
            "source_receipt_sha256": item.source_receipt_sha256,
            "correction_event_id": item.correction_event_id,
            "correction_receipt_sha256": item.correction_receipt_sha256,
            "source_owner": item.source_owner,
            "source_signature_hex": item.source_signature_hex,
        }
        for item in frontier.results
    ]


def revalidation_record(
    manifest_sha256: str, frontier: RevalidationFrontier,
) -> dict:
    if not isinstance(frontier, RevalidationFrontier):
        _invalid("BAMF_C09_REVALIDATION_FRONTIER_REQUIRED")
    body = {
        "event": REVALIDATION_EVENT,
        "accepted_manifest_sha256": manifest_sha256,
        "frontier": _revalidation_payload(frontier),
    }
    return {"event_id": hashlib.sha256(_canonical(body)).hexdigest(), **body}


def frontier_from_record(record: dict) -> RevalidationFrontier:
    try:
        results = tuple(sorted((
            RevalidatedArtifact(
                artifact_id=item["artifact_id"],
                immediate_dependencies=tuple(sorted(
                    DependencyRef(DependencyKind(ref["kind"]), ref["key"])
                    for ref in item["immediate_dependencies"]
                )),
                content_digest=item["content_digest"],
                eligible=item["eligible"],
                source_receipt_sha256=item["source_receipt_sha256"],
                correction_event_id=item["correction_event_id"],
                correction_receipt_sha256=item["correction_receipt_sha256"],
                source_owner=item["source_owner"],
                source_signature_hex=item["source_signature_hex"],
            )
            for item in record["frontier"]
        ), key=lambda item: item.artifact_id))
        return RevalidationFrontier(results)
    except (KeyError, TypeError, ValueError):
        _invalid("BAMF_C09_REVALIDATION_LEDGER_INVALID")


def _records_from_bytes(raw: bytes, manifest_sha256: str) -> tuple[dict, ...]:
    if not raw:
        return ()
    records = []
    try:
        for encoded in raw.splitlines(keepends=True):
            if not encoded.endswith(b"\n"):
                _invalid("BAMF_C09_CORRECTION_LEDGER_TRUNCATED")
            item = json.loads(encoded.decode("utf-8"))
            if (not isinstance(item, dict)
                    or item.get("accepted_manifest_sha256") != manifest_sha256
                    or item.get("event") not in {
                        CORRECTION_EVENT, REVALIDATION_EVENT,
                        REMEDIATION_EVENT, DERIVED_CLAIM_EVENT,
                        PROCESS_FAULT_EVENT,
                    }):
                continue
            body = {key: value for key, value in item.items()
                    if key != "event_id"}
            if item.get("event_id") != hashlib.sha256(
                    _canonical(body)).hexdigest():
                _invalid("BAMF_C09_CORRECTION_LEDGER_DRIFT")
            records.append(item)
    except (UnicodeDecodeError, json.JSONDecodeError):
        _invalid("BAMF_C09_CORRECTION_LEDGER_INVALID")
    by_id = {}
    ordered = []
    for item in records:
        event_id = item["event_id"]
        prior = by_id.get(event_id)
        if prior is not None and prior != item:
            _invalid("BAMF_C09_CORRECTION_LEDGER_CONFLICT")
        if prior is None:
            by_id[event_id] = item
            ordered.append(item)
    return tuple(ordered)


def _read_records_unlocked(
    run_dir: Path, manifest_sha256: str,
) -> tuple[dict, ...]:
    path = _ledger_path(run_dir)
    if not path.exists():
        return ()
    if path.is_symlink() or not path.is_file():
        _invalid("BAMF_C09_CORRECTION_LEDGER_UNSAFE")
    try:
        raw = path.read_bytes()
    except OSError:
        _invalid("BAMF_C09_CORRECTION_LEDGER_INVALID")
    return _records_from_bytes(raw, manifest_sha256)


def _same_history_state(committed: dict | None, state: dict) -> bool:
    return (committed is not None
            and committed["event_ids"] == state["event_ids"]
            and committed["records_sha256"] == state["records_sha256"])


def _validate_transaction_record(transaction: dict) -> dict:
    record = transaction["record"]
    manifest_sha256 = transaction["accepted_manifest_sha256"]
    if (record.get("accepted_manifest_sha256") != manifest_sha256
            or record.get("event") not in {
                CORRECTION_EVENT, REVALIDATION_EVENT,
                REMEDIATION_EVENT, DERIVED_CLAIM_EVENT,
                PROCESS_FAULT_EVENT,
            }):
        _invalid("BAMF_C09_CORRECTION_LEDGER_INVALID")
    body = {key: value for key, value in record.items() if key != "event_id"}
    if record.get("event_id") != hashlib.sha256(_canonical(body)).hexdigest():
        _invalid("BAMF_C09_CORRECTION_LEDGER_DRIFT")
    return record


def _recover_transaction(run_dir: Path, manifest_sha256: str) -> None:
    transaction = _read_transaction(run_dir, manifest_sha256)
    if transaction is None:
        return
    record = _validate_transaction_record(transaction)
    path = _ledger_path(run_dir)
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
    prior = _records_from_bytes(prefix, manifest_sha256)
    prior_state = _history_state(prior)
    expected_prior = {
        "event_ids": transaction["prior_event_ids"],
        "records_sha256": transaction["prior_records_sha256"],
    }
    if prior_state != expected_prior:
        _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")
    target = (*prior, record)
    target_state = _history_state(target)
    expected_target = {
        "event_ids": transaction["target_event_ids"],
        "records_sha256": transaction["target_records_sha256"],
    }
    if target_state != expected_target:
        _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")
    committed = _committed_history(run_dir, manifest_sha256)
    committed_is_prior = (
        committed is None and not prior
    ) or _same_history_state(committed, prior_state)
    committed_is_target = _same_history_state(committed, target_state)
    suffix = raw[prior_size:]
    record_line = _canonical(record) + b"\n"
    if not suffix:
        if not committed_is_prior:
            _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")
        _clear_transaction(run_dir, manifest_sha256)
        return
    if suffix == record_line:
        if not (committed_is_prior or committed_is_target):
            _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")
        full = _records_from_bytes(raw, manifest_sha256)
        if _history_state(full) != target_state:
            _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")
        data_plane().sync_event_ledger(run_dir)
        _commit_history_and_clear(run_dir, manifest_sha256, full)
        return
    if record_line.startswith(suffix):
        if not committed_is_prior:
            _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")
        descriptor = os.open(
            path,
            os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            os.ftruncate(descriptor, prior_size)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        data_plane().sync_event_ledger(run_dir)
        _clear_transaction(run_dir, manifest_sha256)
        return
    _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")


def read_records(run_dir: Path, manifest_sha256: str) -> tuple[dict, ...]:
    with _ledger_lock(run_dir):
        _recover_transaction(run_dir, manifest_sha256)
        result = _read_records_unlocked(run_dir, manifest_sha256)
        if (not _ledger_path(run_dir).exists()
                and _committed_history(run_dir, manifest_sha256) is not None):
            _invalid("BAMF_C09_CORRECTION_LEDGER_MISSING")
        _verify_committed_history(run_dir, manifest_sha256, result)
        return result


def accepted_correction_id(
    manifest_sha256: str, event: CorrectionEvent,
) -> str:
    return correction_record(manifest_sha256, event)["event_id"]


def accepted_corrections(
    run_dir: Path, manifest_sha256: str,
    registry: SourceAuthorityRegistry | None,
) -> tuple[tuple[str, CorrectionEvent], ...]:
    records = tuple(
        item for item in read_records(run_dir, manifest_sha256)
        if item["event"] == CORRECTION_EVENT
    )
    if records and not isinstance(registry, SourceAuthorityRegistry):
        _invalid("BAMF_C09_CORRECTION_AUTHORITY_REQUIRED")
    result = []
    for item in records:
        event = event_from_record(item["correction"])
        registry.verify_correction(event)
        result.append((item["event_id"], event))
    return tuple(result)


def append_record(run_dir: Path, manifest_sha256: str, record: dict) -> None:
    run_dir = Path(run_dir)
    with _ledger_lock(run_dir):
        _recover_transaction(run_dir, manifest_sha256)
        prior = _read_records_unlocked(run_dir, manifest_sha256)
        if (not _ledger_path(run_dir).exists()
                and _committed_history(run_dir, manifest_sha256) is not None):
            _invalid("BAMF_C09_CORRECTION_LEDGER_MISSING")
        _verify_committed_history(run_dir, manifest_sha256, prior)
        if any(item["event_id"] == record["event_id"] for item in prior):
            _commit_history(run_dir, manifest_sha256, prior)
            return
        if (record.get("accepted_manifest_sha256") != manifest_sha256
                or record.get("event") not in {
                    CORRECTION_EVENT, REVALIDATION_EVENT,
                    REMEDIATION_EVENT, DERIVED_CLAIM_EVENT,
                    PROCESS_FAULT_EVENT,
                }):
            _invalid("BAMF_C09_CORRECTION_LEDGER_INVALID")
        body = {key: value for key, value in record.items() if key != "event_id"}
        if record.get("event_id") != hashlib.sha256(_canonical(body)).hexdigest():
            _invalid("BAMF_C09_CORRECTION_LEDGER_DRIFT")
        path = _ledger_path(run_dir)
        if path.is_symlink() or (path.exists() and not path.is_file()):
            _invalid("BAMF_C09_CORRECTION_LEDGER_UNSAFE")
        try:
            prior_raw = path.read_bytes() if path.exists() else b""
        except OSError:
            _invalid("BAMF_C09_CORRECTION_LEDGER_INVALID")
        target = (*prior, record)
        prior_state = _history_state(prior)
        target_state = _history_state(target)
        _write_transaction(run_dir, manifest_sha256, {
            "schema_version": HISTORY_TRANSACTION_SCHEMA,
            "state": "PREPARED",
            "run_dir": str(run_dir.resolve()),
            "accepted_manifest_sha256": manifest_sha256,
            "record": record,
            "prior_file_size": len(prior_raw),
            "prior_file_sha256": hashlib.sha256(prior_raw).hexdigest(),
            "prior_event_ids": prior_state["event_ids"],
            "prior_records_sha256": prior_state["records_sha256"],
            "target_event_ids": target_state["event_ids"],
            "target_records_sha256": target_state["records_sha256"],
        })
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            _write_all(descriptor, _canonical(record) + b"\n")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        data_plane().sync_event_ledger(run_dir)
        _commit_history_and_clear(run_dir, manifest_sha256, target)


__all__ = (
    "CORRECTION_EVENT", "REVALIDATION_EVENT", "REMEDIATION_EVENT",
    "DERIVED_CLAIM_EVENT", "PROCESS_FAULT_EVENT", "accepted_correction_id",
    "accepted_corrections", "append_record", "correction_record",
    "frontier_from_record", "read_records", "revalidation_record",
)
