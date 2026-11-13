"""Canonical publication codec for immutable BAMF delivery manifests."""
from __future__ import annotations

import json

from .contracts import (
    BamfDeliveryManifest, CommitReceipt, ComponentReceipt, EgmReceipt, EgmStatus,
    IssueReceipt, OperatorCommandReceipt, ProofReceipt, ProofState, ReceiptStatus,
    canonical, invalid, require,
)

_MANIFEST_KEYS = frozenset((
    "schema", "components", "issues", "commits", "proofs", "egm",
    "operator_commands", "software_delivery_status", "student_mastery_status",
))
_SEALED_KEYS = _MANIFEST_KEYS | frozenset(("manifest_sha256",))


def seal_manifest(manifest: BamfDeliveryManifest) -> dict:
    """Return a self-verifying public record without mutating the manifest payload."""
    record = json.loads(canonical(manifest.to_record()))
    return {**record, "manifest_sha256": manifest.digest()}


def _exact(record: object, keys: frozenset[str], reason: str) -> dict:
    require(type(record) is dict and set(record) == keys, reason)
    return record


def _records(value: object, reason: str) -> list[dict]:
    require(type(value) is list and all(type(item) is dict for item in value), reason)
    return value


def load_manifest_record(record: object) -> BamfDeliveryManifest:
    """Decode and authenticate one exact sealed manifest record."""
    row = _exact(record, _SEALED_KEYS, "SEALED_MANIFEST_KEYS")
    try:
        components = tuple(ComponentReceipt(
            item["component_id"], item["owner_issue"], item["head_sha"],
            ReceiptStatus(item["status"]), item["evidence_ref"])
            for item in _records(row["components"], "COMPONENT_RECORDS"))
        issues = tuple(IssueReceipt(
            item["issue"], item["issue_key"], item["state"],
            ReceiptStatus(item["status"]), item["head_sha"], item["evidence_ref"])
            for item in _records(row["issues"], "ISSUE_RECORDS"))
        commits = tuple(CommitReceipt(
            item["sha"], item["owner_issue"], item["role"])
            for item in _records(row["commits"], "COMMIT_RECORDS"))
        proofs = tuple(ProofReceipt(
            item["proof_id"], ProofState(item["state"]), item["input_schema"],
            item["output_schema"], item["evidence_ref"], item["observed"])
            for item in _records(row["proofs"], "PROOF_RECORDS"))
        egm = tuple(EgmReceipt(
            item["reviewer"], EgmStatus(item["status"]), item["candidate_sha"],
            item["report_ref"])
            for item in _records(row["egm"], "EGM_RECORDS"))
        commands = tuple(OperatorCommandReceipt(
            item["command_id"], tuple(item["argv"]), ProofState(item["state"]),
            item["parser_test"], item["evidence_ref"])
            for item in _records(row["operator_commands"], "COMMAND_RECORDS"))
        manifest = BamfDeliveryManifest(
            components, issues, commits, proofs, egm, commands,
            software_delivery_status=row["software_delivery_status"],
            student_mastery_status=row["student_mastery_status"],
            schema=row["schema"],
        )
    except (KeyError, TypeError, ValueError):
        invalid("SEALED_MANIFEST_VALUE")
    require(row["manifest_sha256"] == manifest.digest(), "MANIFEST_DIGEST")
    return manifest
