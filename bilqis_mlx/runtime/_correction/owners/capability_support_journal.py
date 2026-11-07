"""Durable C09 hold state for accepted capability-support custody."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import uuid

from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef
from .atlas_revalidation_common import _invalid
from .atlas_revalidation_evidence import CorrectionEvent

SCHEMA = "bilqis.c09.capability-support-hold/v1"


def journal_path(run_dir: Path, manifest_sha256: str, capability_id: str) -> Path:
    key = hashlib.sha256(capability_id.encode("utf-8")).hexdigest()
    return Path(run_dir) / "c09-capability-support" / manifest_sha256 / f"{key}.json"


def _event_record(event: CorrectionEvent) -> dict:
    return {
        "event_id": event.event_id,
        "dependency": {"kind": event.dependency.kind.value, "key": event.dependency.key},
        "source_owner": event.source_owner,
        "source_receipt_sha256": event.source_receipt_sha256,
        "old_evidence_sha256": event.old_evidence_sha256,
        "new_evidence_sha256": event.new_evidence_sha256,
        "source_time": event.source_time,
        "effective_time": event.effective_time,
        "observed_at": event.observed_at,
        "recorded_at": event.recorded_at,
        "reason_code": event.reason_code,
        "source_signature_hex": event.source_signature_hex,
        "supersedes_event_ids": list(event.supersedes_event_ids),
    }


def event_from_record(record: dict) -> CorrectionEvent:
    try:
        dependency = record["dependency"]
        return CorrectionEvent(
            event_id=record["event_id"],
            dependency=DependencyRef(DependencyKind(dependency["kind"]), dependency["key"]),
            source_owner=record["source_owner"],
            source_receipt_sha256=record["source_receipt_sha256"],
            old_evidence_sha256=record["old_evidence_sha256"],
            new_evidence_sha256=record["new_evidence_sha256"],
            source_time=record["source_time"], effective_time=record["effective_time"],
            observed_at=record["observed_at"], recorded_at=record["recorded_at"],
            reason_code=record["reason_code"],
            source_signature_hex=record["source_signature_hex"],
            supersedes_event_ids=tuple(record.get("supersedes_event_ids", ())),
        )
    except (KeyError, TypeError, ValueError):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_INVALID")


def write_journal(path: Path, *, capability_id: str, manifest_sha256: str,
                  artifact_id: str, state: str, event: CorrectionEvent) -> None:
    data = {
        "schema_version": SCHEMA, "capability_id": capability_id,
        "manifest_sha256": manifest_sha256, "artifact_id": artifact_id,
        "state": state, "event": _event_record(event),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read_journal(path: Path) -> dict | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_INVALID")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_INVALID")
    if not isinstance(record, dict) or record.get("schema_version") != SCHEMA:
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_INVALID")
    return record


def clear_journal(path: Path) -> None:
    path.unlink(missing_ok=True)

