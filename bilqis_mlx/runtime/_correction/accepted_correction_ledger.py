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
from bilqis_mlx.runtime.capability_support_journal import (
    _event_record, event_from_record,
)


CORRECTION_EVENT = "BAMF_C09_CORRECTION"
REVALIDATION_EVENT = "BAMF_C09_REVALIDATION"


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


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
    return tuple(ordered)


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


__all__ = (
    "CORRECTION_EVENT", "REVALIDATION_EVENT", "accepted_correction_id",
    "accepted_corrections", "append_record", "correction_record",
    "frontier_from_record", "read_records", "revalidation_record",
)
