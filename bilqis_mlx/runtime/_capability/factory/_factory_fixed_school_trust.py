"""Append-only C05 trust root for one BAMF run's fixed school."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass

from bilqis_mlx.data_plane import data_plane
from bilqis_mlx.runtime.capability_evaluation import _invalid

from ._factory_fixed_school_contract import is_hex


@dataclass(frozen=True)
class FixedSchoolTrust:
    receipt: dict
    cohort: dict
    receipt_raw: bytes
    cohort_raw: bytes


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def wire(value: dict) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode("utf-8")


def _row(run_identity_sha256: str):
    plane = data_plane()
    with plane._lock:
        return plane._db.execute(
            "SELECT run_id,foundation_parent_manifest_sha256,receipt_sha256,"
            "receipt_payload,cohort_sha256,cohort_payload_sha256,cohort_payload "
            "FROM bamf_c05_fixed_school_trust WHERE run_identity_sha256=?",
            (run_identity_sha256,),
        ).fetchone()


def _validate_row(run_identity_sha256: str, row):
    if row is None:
        return None
    (run_id, foundation, receipt_sha, receipt_raw, cohort_sha,
     cohort_payload_sha, cohort_raw) = row
    if (not is_hex(run_identity_sha256) or not isinstance(run_id, str) or not run_id
            or not is_hex(foundation) or not is_hex(receipt_sha)
            or not is_hex(cohort_sha) or not is_hex(cohort_payload_sha)
            or not isinstance(receipt_raw, bytes) or not isinstance(cohort_raw, bytes)
            or _sha(receipt_raw) != receipt_sha
            or _sha(cohort_raw) != cohort_payload_sha):
        _invalid("BAMF_C05_FIXED_SCHOOL_TRUST_DRIFT")
    try:
        receipt = json.loads(receipt_raw)
        cohort = json.loads(cohort_raw)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        _invalid("BAMF_C05_FIXED_SCHOOL_TRUST_DRIFT")
        raise AssertionError
    if (receipt.get("run_id") != run_id
            or receipt.get("run_identity_sha256") != run_identity_sha256
            or receipt.get("foundation_parent_manifest_sha256") != foundation
            or receipt.get("cohort_sha256") != cohort_sha
            or cohort.get("cohort_sha256") != cohort_sha):
        _invalid("BAMF_C05_FIXED_SCHOOL_TRUST_DRIFT")
    return FixedSchoolTrust(receipt, cohort, receipt_raw, cohort_raw)


def load_fixed_school_trust(run_identity_sha256: str):
    """Read and verify C05's external immutable receipt/cohort authority."""
    return _validate_row(run_identity_sha256, _row(run_identity_sha256))


def publish_fixed_school_trust(receipt: dict, cohort: dict):
    """Seal once; replay is lawful only for byte-identical C05 authority."""
    run_identity = receipt.get("run_identity_sha256")
    run_id = receipt.get("run_id")
    foundation = receipt.get("foundation_parent_manifest_sha256")
    cohort_sha = receipt.get("cohort_sha256")
    if (not is_hex(run_identity) or not isinstance(run_id, str) or not run_id
            or not is_hex(foundation) or not is_hex(cohort_sha)
            or cohort.get("cohort_sha256") != cohort_sha):
        _invalid("BAMF_C05_FIXED_SCHOOL_TRUST_INVALID")
    receipt_raw, cohort_raw = wire(receipt), wire(cohort)
    values = (
        run_identity, run_id, foundation, _sha(receipt_raw), receipt_raw,
        cohort_sha, _sha(cohort_raw), cohort_raw,
    )
    existing = _validate_row(run_identity, _row(run_identity))
    if existing is not None:
        if (existing.receipt_raw != receipt_raw
                or existing.cohort_raw != cohort_raw):
            _invalid("BAMF_C05_FIXED_SCHOOL_TRUST_CONFLICT")
        return existing
    plane = data_plane()
    try:
        with plane.transaction():
            row = plane._db.execute(
                "SELECT run_id,foundation_parent_manifest_sha256,receipt_sha256,"
                "receipt_payload,cohort_sha256,cohort_payload_sha256,cohort_payload "
                "FROM bamf_c05_fixed_school_trust WHERE run_identity_sha256=?",
                (run_identity,),
            ).fetchone()
            if row is None:
                plane._db.execute(
                    "INSERT INTO bamf_c05_fixed_school_trust("
                    "run_identity_sha256,run_id,foundation_parent_manifest_sha256,"
                    "receipt_sha256,receipt_payload,cohort_sha256,"
                    "cohort_payload_sha256,cohort_payload) VALUES(?,?,?,?,?,?,?,?)",
                    values,
                )
            else:
                checked = _validate_row(run_identity, row)
                if (checked.receipt_raw != receipt_raw
                        or checked.cohort_raw != cohort_raw):
                    _invalid("BAMF_C05_FIXED_SCHOOL_TRUST_CONFLICT")
    except sqlite3.IntegrityError:
        _invalid("BAMF_C05_FIXED_SCHOOL_TRUST_CONFLICT")
    stored = load_fixed_school_trust(run_identity)
    if (stored is None or stored.receipt_raw != receipt_raw
            or stored.cohort_raw != cohort_raw):
        _invalid("BAMF_C05_FIXED_SCHOOL_TRUST_DRIFT")
    return stored


__all__ = ()
