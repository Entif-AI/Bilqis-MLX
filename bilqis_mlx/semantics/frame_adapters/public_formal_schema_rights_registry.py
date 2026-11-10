"""Hash-chained A13 owner registry for PUBLIC_FORMAL motif-schema rights."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from ..frame_schema import SourceSpan
from .common import _adapter_fail


REGISTRY_SCHEMA = "bilqis.public-formal-schema-rights-registry/v3"
_REGISTRY_DIR = Path(__file__).with_name("public_formal_schema_rights_registry")
_ROOT_REGISTRY_SHA256 = (
    "cf9eddb0ab1b8a56b39bff9f9eb391fccf8000303958790d7edd1f862e86fcb6"
)
_REGISTRY_SHA256 = _ROOT_REGISTRY_SHA256
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_FAMILIES = frozenset(("boolean", "micro", "numeric"))
_MAX_REGISTRY_CHAIN_LENGTH = 256
_ENTRY_KEYS = frozenset((
    "family", "schema_id", "revision", "evidence_sha256", "decisions",
))
_TOP_KEYS = frozenset((
    "schema", "atlas_bundle_id", "semantic_release", "source_bundle_id",
    "rights_epoch", "correction_generation", "predecessor_registry_sha256",
    "entries",
))


def _fail(reason: str) -> None:
    _adapter_fail(reason, "<schema-rights>", SourceSpan(0, 0), "<schema>")


def _effective_revoked(entry: dict, current_epoch: int) -> bool:
    """Fold one append-only owner decision stream into current revocation state."""
    state = None
    revoked_epoch = None
    last_epoch = -1
    for decision in entry.get("decisions", ()):
        if (
            not isinstance(decision, dict)
            or set(decision) != {"action", "rights_epoch"}
            or decision.get("action") not in {"ISSUE", "REVOKE"}
            or type(decision.get("rights_epoch")) is not int
            or decision["rights_epoch"] < 0
            or decision["rights_epoch"] < last_epoch
            or decision["rights_epoch"] > current_epoch
        ):
            _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_LINEAGE_INVALID")
        epoch = decision["rights_epoch"]
        if decision["action"] == "ISSUE":
            if state is False or (
                state is True and revoked_epoch is not None and epoch <= revoked_epoch
            ):
                _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_LINEAGE_INVALID")
            state = False
        else:
            if state is not False:
                _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_LINEAGE_INVALID")
            state = True
            revoked_epoch = epoch
        last_epoch = epoch
    if state is None:
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_LINEAGE_INVALID")
    return state


def _validate_snapshot(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != _TOP_KEYS:
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_REGISTRY_INVALID")
    predecessor = value["predecessor_registry_sha256"]
    entries = value["entries"]
    if (
        value["schema"] != REGISTRY_SCHEMA
        or any(
            not isinstance(value[name], str) or not _SHA256.fullmatch(value[name])
            for name in ("atlas_bundle_id", "semantic_release", "source_bundle_id")
        )
        or type(value["rights_epoch"]) is not int or value["rights_epoch"] < 0
        or type(value["correction_generation"]) is not int
        or value["correction_generation"] < 0
        or (predecessor is not None
            and (not isinstance(predecessor, str) or not _SHA256.fullmatch(predecessor)))
        or not isinstance(entries, list) or not entries
    ):
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_REGISTRY_INVALID")
    identities = []
    for entry in entries:
        if (
            not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS
            or entry.get("family") not in _FAMILIES
            or not isinstance(entry.get("schema_id"), str) or not entry["schema_id"]
            or type(entry.get("revision")) is not int or entry["revision"] < 1
            or not isinstance(entry.get("evidence_sha256"), str)
            or not _SHA256.fullmatch(entry["evidence_sha256"])
            or not isinstance(entry.get("decisions"), list) or not entry["decisions"]
        ):
            _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_REGISTRY_INVALID")
        _effective_revoked(entry, value["rights_epoch"])
        identities.append((entry["family"], entry["schema_id"], entry["revision"]))
    if identities != sorted(identities) or len(identities) != len(set(identities)):
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_REGISTRY_INVALID")
    return value


def _read_snapshot(digest: str) -> dict:
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_REGISTRY_INVALID")
    path = _REGISTRY_DIR / (digest + ".json")
    if path.is_symlink() or not path.is_file():
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_REGISTRY_MISSING")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeError, ValueError):
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_REGISTRY_INVALID")
    if hashlib.sha256(raw).hexdigest() != digest:
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_REGISTRY_INVALID")
    return _validate_snapshot(value)


def _entry_map(snapshot: dict) -> dict:
    return {
        (entry["family"], entry["schema_id"], entry["revision"]): entry
        for entry in snapshot["entries"]
    }


def _validate_transition(parent: dict, child: dict, parent_digest: str) -> None:
    if (
        child["predecessor_registry_sha256"] != parent_digest
        or tuple(child[name] for name in (
            "atlas_bundle_id", "semantic_release", "source_bundle_id",
        )) != tuple(parent[name] for name in (
            "atlas_bundle_id", "semantic_release", "source_bundle_id",
        ))
        or child["rights_epoch"] < parent["rights_epoch"]
        or child["correction_generation"] < parent["correction_generation"]
    ):
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_LINEAGE_INVALID")
    before = _entry_map(parent)
    after = _entry_map(child)
    if set(before) != set(after):
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_LINEAGE_INVALID")
    for identity, prior in before.items():
        current = after[identity]
        if current["evidence_sha256"] != prior["evidence_sha256"]:
            _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_LINEAGE_INVALID")
        old_decisions = prior["decisions"]
        new_decisions = current["decisions"]
        if new_decisions[:len(old_decisions)] != old_decisions:
            _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_LINEAGE_INVALID")
        appended = new_decisions[len(old_decisions):]
        if any(
            decision["rights_epoch"] != child["rights_epoch"]
            for decision in appended
        ):
            _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_LINEAGE_INVALID")
        _effective_revoked(current, child["rights_epoch"])


def _load_registry() -> dict:
    """Read current owner state only after verifying its complete predecessor chain."""
    digest = _REGISTRY_SHA256
    chain = []
    seen = set()
    while True:
        if digest in seen or len(chain) >= _MAX_REGISTRY_CHAIN_LENGTH:
            _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_LINEAGE_INVALID")
        seen.add(digest)
        snapshot = _read_snapshot(digest)
        chain.append((digest, snapshot))
        predecessor = snapshot["predecessor_registry_sha256"]
        if predecessor is None:
            break
        digest = predecessor
    if chain[-1][0] != _ROOT_REGISTRY_SHA256:
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_LINEAGE_INVALID")
    ordered = tuple(reversed(chain))
    for (parent_digest, parent), (_child_digest, child) in zip(
        ordered, ordered[1:]
    ):
        _validate_transition(parent, child, parent_digest)
    return ordered[-1][1]


__all__ = ("REGISTRY_SCHEMA", "_effective_revoked", "_load_registry")
