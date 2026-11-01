"""Exact JSON round-trip for the B07/B12 retained motif allocation snapshot."""
from __future__ import annotations

from dataclasses import asdict
from typing import Mapping

from bilqis_mlx.learning.atlas_engram import MotifKey, MotifManifest, MotifMember, MotifSlot
from bilqis_mlx.learning.atlas_engram_transaction import (
    MotifAliasArtifact, MotifAllocationSnapshot,
)

_INVALID_MOTIF_SIDECAR = "BAMF_MOTIF_SIDECAR_INVALID"


def _exact(record: object, fields: set[str]) -> Mapping:
    if not isinstance(record, Mapping) or set(record) != fields:
        raise ValueError(_INVALID_MOTIF_SIDECAR)
    return record


def _member(record: object) -> MotifMember:
    row = _exact(record, {
        "role_id", "occurrence_index", "state", "target_kind", "target_ids",
        "type_ids", "schema_version",
    })
    return MotifMember(
        row["role_id"], row["occurrence_index"], row["state"], row["target_kind"],
        tuple(row["target_ids"]), tuple(row["type_ids"]), row["schema_version"])


def _key(record: object) -> MotifKey:
    row = _exact(record, {
        "kind", "semantic_release", "frame_schema_id", "frame_schema_revision",
        "members", "relation_signature", "scope", "schema_version",
    })
    return MotifKey(
        row["kind"], row["semantic_release"], row["frame_schema_id"],
        row["frame_schema_revision"], tuple(_member(item) for item in row["members"]),
        row["relation_signature"], row["scope"], row["schema_version"])


def _manifest(record: object) -> MotifManifest:
    row = _exact(record, {"semantic_release", "slots", "capacity", "schema_version"})
    slots = tuple(
        MotifSlot(item["slot_id"], _key(item["key"]))
        for item in row["slots"]
        if _exact(item, {"slot_id", "key"})
    )
    return MotifManifest(row["semantic_release"], slots, row["capacity"], row["schema_version"])


def _alias(record: object) -> MotifAliasArtifact:
    row = _exact(record, {
        "old_release", "old_key_digest", "new_release", "new_key_digest",
        "source_attestation_digest", "schema_version",
    })
    return MotifAliasArtifact(**row)


def snapshot_to_record(snapshot: MotifAllocationSnapshot) -> dict:
    if type(snapshot) is not MotifAllocationSnapshot:
        raise ValueError(_INVALID_MOTIF_SIDECAR)
    snapshot.__post_init__()
    return {
        "schema": "bilqis.mlx.bamf-motif-allocation/v1",
        "snapshot": asdict(snapshot),
        "snapshot_digest": snapshot.digest,
        "manifest_digest": snapshot.manifest.digest,
    }


def snapshot_from_record(record: object) -> MotifAllocationSnapshot:
    outer = _exact(record, {"schema", "snapshot", "snapshot_digest", "manifest_digest"})
    if outer["schema"] != "bilqis.mlx.bamf-motif-allocation/v1":
        raise ValueError(_INVALID_MOTIF_SIDECAR)
    row = _exact(outer["snapshot"], {
        "manifest", "observed_uses", "pending_keys", "aliases", "schema_version",
    })
    snapshot = MotifAllocationSnapshot(
        _manifest(row["manifest"]),
        tuple((item[0], item[1]) for item in row["observed_uses"]),
        tuple(_key(item) for item in row["pending_keys"]),
        tuple(_alias(item) for item in row["aliases"]),
        row["schema_version"],
    )
    if (snapshot.digest != outer["snapshot_digest"]
            or snapshot.manifest.digest != outer["manifest_digest"]):
        raise ValueError(_INVALID_MOTIF_SIDECAR)
    return snapshot
