"""Durable C09 hold state for accepted capability-support custody."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import uuid

from bilqis_mlx.data_plane import data_plane
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef
from .atlas_revalidation_common import _invalid
from .atlas_revalidation_evidence import CorrectionEvent, StateTransition

SCHEMA = "bilqis.c09.capability-support-hold/v1"
MARKER_SCHEMA = "bilqis.c09.capability-support-hold-seen/v1"
COMMITMENT_SCHEMA = "bilqis.c09.capability-support-hold-commitment/v1"


def journal_path(run_dir: Path, manifest_sha256: str, capability_id: str) -> Path:
    key = hashlib.sha256(capability_id.encode("utf-8")).hexdigest()
    return Path(run_dir) / "c09-capability-support" / manifest_sha256 / f"{key}.json"


def _marker_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".seen")


def _commitment(capability_id: str, manifest_sha256: str,
                artifact_id: str) -> tuple[str, bytes]:
    record = {
        "schema_version": COMMITMENT_SCHEMA,
        "capability_id": capability_id,
        "manifest_sha256": manifest_sha256,
        "artifact_id": artifact_id,
    }
    raw = json.dumps(
        record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest(), raw


def _commit_seen(capability_id: str, manifest_sha256: str,
                 artifact_id: str) -> None:
    digest, raw = _commitment(capability_id, manifest_sha256, artifact_id)
    data_plane().put_object(digest, raw)


def _seen(capability_id: str, manifest_sha256: str,
          artifact_id: str) -> bool:
    digest, raw = _commitment(capability_id, manifest_sha256, artifact_id)
    try:
        stored = data_plane().get_object(digest)
    except ValueError:
        return False
    if stored != raw:
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_COMMITMENT_DRIFT")
    return True


def _marker_identity(capability_id: str, manifest_sha256: str,
                     artifact_id: str) -> dict:
    return {
        "schema_version": MARKER_SCHEMA,
        "capability_id": capability_id,
        "manifest_sha256": manifest_sha256,
        "artifact_id": artifact_id,
    }


def _atomic_json(path: Path, data: dict, *, replace_existing: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    if replace_existing:
        os.replace(temporary, path)
    else:
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
        finally:
            temporary.unlink(missing_ok=True)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


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


def _transition_record(transition: StateTransition | None) -> dict | None:
    if transition is None:
        return None
    return {
        "artifact_id": transition.artifact_id,
        "previous_content_digest": transition.previous_content_digest,
        "new_content_digest": transition.new_content_digest,
        "previous_eligible": transition.previous_eligible,
        "new_eligible": transition.new_eligible,
        "source_receipt_sha256": transition.source_receipt_sha256,
        "correction_event_id": transition.correction_event_id,
        "correction_receipt_sha256": transition.correction_receipt_sha256,
        "source_owner": transition.source_owner,
        "source_signature_hex": transition.source_signature_hex,
        "immediate_dependencies": [
            {"kind": ref.kind.value, "key": ref.key}
            for ref in transition.immediate_dependencies
        ],
        "changed": transition.changed,
    }


def transition_from_record(record: dict | None) -> StateTransition | None:
    if record is None:
        return None
    try:
        return StateTransition(
            artifact_id=record["artifact_id"],
            previous_content_digest=record["previous_content_digest"],
            new_content_digest=record["new_content_digest"],
            previous_eligible=record["previous_eligible"],
            new_eligible=record["new_eligible"],
            source_receipt_sha256=record["source_receipt_sha256"],
            correction_event_id=record["correction_event_id"],
            correction_receipt_sha256=record["correction_receipt_sha256"],
            source_owner=record["source_owner"],
            source_signature_hex=record["source_signature_hex"],
            immediate_dependencies=tuple(sorted(
                DependencyRef(DependencyKind(item["kind"]), item["key"])
                for item in record["immediate_dependencies"])),
            changed=record["changed"],
        )
    except (KeyError, TypeError, ValueError):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_INVALID")


def write_journal(path: Path, *, capability_id: str, manifest_sha256: str,
                  artifact_id: str, state: str, event: CorrectionEvent,
                  transition: StateTransition | None = None) -> None:
    if state not in {"HELD", "CLEARED", "REQUALIFICATION_REQUIRED"}:
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_INVALID")
    if (state == "HELD") != (transition is None):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_INVALID")
    marker = _marker_identity(capability_id, manifest_sha256, artifact_id)
    _commit_seen(capability_id, manifest_sha256, artifact_id)
    marker_path = _marker_path(path)
    _atomic_json(marker_path, marker, replace_existing=False)
    try:
        current_marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_INVALID")
    if current_marker != marker:
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_DRIFT")
    data = {
        "schema_version": SCHEMA, "capability_id": capability_id,
        "manifest_sha256": manifest_sha256, "artifact_id": artifact_id,
        "state": state, "event": _event_record(event),
        "transition": _transition_record(transition),
    }
    _atomic_json(path, data, replace_existing=True)


def read_journal(path: Path, *, capability_id: str,
                 manifest_sha256: str, artifact_id: str) -> dict | None:
    marker_path = _marker_path(path)
    marker_exists = marker_path.exists()
    journal_exists = path.exists()
    if not marker_exists and not journal_exists:
        if _seen(capability_id, manifest_sha256, artifact_id):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_MISSING")
        return None
    if (not marker_exists or not journal_exists
            or marker_path.is_symlink() or not marker_path.is_file()
            or path.is_symlink() or not path.is_file()):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_INVALID")
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_INVALID")
    if (not isinstance(marker, dict)
            or marker.get("schema_version") != MARKER_SCHEMA
            or not isinstance(record, dict)
            or record.get("schema_version") != SCHEMA
            or any(marker.get(key) != record.get(key)
                   for key in ("capability_id", "manifest_sha256", "artifact_id"))):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_HOLD_INVALID")
    if not _seen(capability_id, manifest_sha256, artifact_id):
        _invalid("BAMF_C09_CAPABILITY_SUPPORT_COMMITMENT_MISSING")
    return record

