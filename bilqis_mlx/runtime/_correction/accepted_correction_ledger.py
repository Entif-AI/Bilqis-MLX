"""Durable codec and persistence for accepted-generation C09 evidence."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

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
    return _canonical({
        "schema_version": HISTORY_COMMITMENT_SCHEMA,
        "run_dir": str(Path(run_dir).resolve()),
        "accepted_manifest_sha256": manifest_sha256,
        "event_ids": [record["event_id"] for record in records],
        "records_sha256": hashlib.sha256(_canonical(records)).hexdigest(),
    })


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
    event_ids = [record["event_id"] for record in records]
    records_sha256 = hashlib.sha256(_canonical(records)).hexdigest()
    if (committed["event_ids"] != event_ids
            or committed["records_sha256"] != records_sha256):
        _invalid("BAMF_C09_CORRECTION_HISTORY_COMMITMENT_DRIFT")


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


def read_records(run_dir: Path, manifest_sha256: str) -> tuple[dict, ...]:
    path = Path(run_dir) / "events.jsonl"
    if not path.exists():
        if _committed_history(run_dir, manifest_sha256) is not None:
            _invalid("BAMF_C09_CORRECTION_LEDGER_MISSING")
        return ()
    if path.is_symlink() or not path.is_file():
        _invalid("BAMF_C09_CORRECTION_LEDGER_UNSAFE")
    records = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if not line.endswith("\n"):
                    _invalid("BAMF_C09_CORRECTION_LEDGER_TRUNCATED")
                item = json.loads(line)
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
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
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
    result = tuple(ordered)
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
    prior = read_records(run_dir, manifest_sha256)
    if any(item["event_id"] == record["event_id"] for item in prior):
        _commit_history(run_dir, manifest_sha256, prior)
        return
    path = Path(run_dir) / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, _canonical(record) + b"\n")
        os.fsync(fd)
    finally:
        os.close(fd)
    data_plane().sync_event_ledger(run_dir)
    _commit_history(run_dir, manifest_sha256, (*prior, record))


__all__ = (
    "CORRECTION_EVENT", "REVALIDATION_EVENT", "REMEDIATION_EVENT",
    "DERIVED_CLAIM_EVENT", "PROCESS_FAULT_EVENT", "accepted_correction_id",
    "accepted_corrections", "append_record", "correction_record",
    "frontier_from_record", "read_records", "revalidation_record",
)
