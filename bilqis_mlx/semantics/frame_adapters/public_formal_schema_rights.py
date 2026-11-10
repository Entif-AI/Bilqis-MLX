"""A13 owner authority for current PUBLIC_FORMAL motif-schema rights."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path

from ..atlas.snapshot import AtlasArtifactSelection
from ..atlas_features.formal import source_family_for_adapter
from ..context_eligibility import (
    PUBLIC_FORMAL, ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
)
from ..frame_schema import FrameSchema, SourceSpan
from ..released_frame_schemas import lookup_source_pinned_frame_schema
from .common import PUBLIC_FORMAL_TIMELESS_EPOCH, _SHA256, _adapter_fail


REGISTRY_SCHEMA = "bilqis.public-formal-schema-rights-registry/v1"
AUTHORITY_SCHEMA = "bilqis.public-formal-schema-rights-authority/v1"
IDENTITY_SCHEMA = "bilqis.public-formal-schema-rights-identity/v1"
_REGISTRY = Path(__file__).with_name("public_formal_schema_rights_v1.json")
_REGISTRY_SHA256 = "e1980c267bc0faca7f18d7c2a8487da98011de5ffa45524c155151fe7d7b5e25"
_FAMILIES = frozenset(("boolean", "micro", "numeric"))
_ISSUER = object()


def _fail(reason: str, adapter_id: str = "<schema-rights>") -> None:
    _adapter_fail(reason, adapter_id, SourceSpan(0, 0), "<schema>")


def _load_registry() -> dict:
    if _REGISTRY.is_symlink() or not _REGISTRY.is_file():
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_REGISTRY_MISSING")
    try:
        raw = _REGISTRY.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeError, ValueError):
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_REGISTRY_INVALID")
    entries = value.get("entries") if isinstance(value, dict) else None
    if (
        hashlib.sha256(raw).hexdigest() != _REGISTRY_SHA256
        or set(value) != {
            "schema", "atlas_bundle_id", "semantic_release", "source_bundle_id",
            "rights_epoch", "correction_generation", "entries",
        }
        or value["schema"] != REGISTRY_SCHEMA
        or not all(isinstance(value[name], str) and value[name] for name in (
            "atlas_bundle_id", "semantic_release", "source_bundle_id"))
        or not _SHA256.fullmatch(value["semantic_release"])
        or type(value["rights_epoch"]) is not int or value["rights_epoch"] < 0
        or type(value["correction_generation"]) is not int
        or value["correction_generation"] < 0
        or not isinstance(entries, list) or not entries
    ):
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_REGISTRY_INVALID")
    keys = {"family", "schema_id", "revision", "evidence_sha256", "revoked"}
    identities = []
    for entry in entries:
        if (
            not isinstance(entry, dict) or set(entry) != keys
            or not all(isinstance(entry[name], str) and entry[name] for name in (
                "family", "schema_id", "evidence_sha256"))
            or entry["family"] not in _FAMILIES
            or not _SHA256.fullmatch(entry["evidence_sha256"])
            or type(entry["revision"]) is not int or entry["revision"] < 1
            or type(entry["revoked"]) is not bool
        ):
            _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_REGISTRY_INVALID")
        identities.append((entry["family"], entry["schema_id"], entry["revision"]))
    if identities != sorted(identities) or len(identities) != len(set(identities)):
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_REGISTRY_INVALID")
    return value


@dataclass(frozen=True, init=False)
class SourceSchemaRightsAuthority:
    """Opaque source-owner view of the current schema-right decision registry."""

    atlas_selection: AtlasArtifactSelection
    rights_epoch: int
    correction_generation: int
    registry_sha256: str
    schema: str = AUTHORITY_SCHEMA
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self) -> None:
        registry = _load_registry()
        selection = self.atlas_selection
        if type(selection) is not AtlasArtifactSelection:
            _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_SOURCE_REQUIRED")
        selection.__post_init__()
        if (
            getattr(self, "_issuance", None) is not _ISSUER
            or (selection.bundle_id, selection.release_sha256, selection.source_bundle_id)
            != (
                registry["atlas_bundle_id"], registry["semantic_release"],
                registry["source_bundle_id"],
            )
            or self.rights_epoch != registry["rights_epoch"]
            or self.correction_generation != registry["correction_generation"]
            or self.registry_sha256 != _REGISTRY_SHA256
            or self.schema != AUTHORITY_SCHEMA
        ):
            _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_AUTHORITY_INVALID")


def issue_source_schema_rights_authority(
    atlas_selection: AtlasArtifactSelection,
) -> SourceSchemaRightsAuthority:
    """Issue current rights only from the hash-pinned A13 owner registry."""
    if type(atlas_selection) is not AtlasArtifactSelection:
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_SOURCE_REQUIRED")
    atlas_selection.__post_init__()
    registry = _load_registry()
    expected = (
        registry["atlas_bundle_id"], registry["semantic_release"],
        registry["source_bundle_id"],
    )
    if expected != (
        atlas_selection.bundle_id, atlas_selection.release_sha256,
        atlas_selection.source_bundle_id,
    ):
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_SOURCE_NOT_AUTHORIZED")
    authority = object.__new__(SourceSchemaRightsAuthority)
    for name, value in (
        ("atlas_selection", atlas_selection),
        ("rights_epoch", registry["rights_epoch"]),
        ("correction_generation", registry["correction_generation"]),
        ("registry_sha256", _REGISTRY_SHA256),
        ("schema", AUTHORITY_SCHEMA),
        ("_issuance", _ISSUER),
    ):
        object.__setattr__(authority, name, value)
    authority.__post_init__()
    return authority


def source_schema_rights_frontier(
    authority: SourceSchemaRightsAuthority,
) -> SourceFrontier:
    """Project only the owner-current epochs; schema grants are rederived on use."""
    if type(authority) is not SourceSchemaRightsAuthority:
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_AUTHORITY_REQUIRED")
    authority.__post_init__()
    return SourceFrontier(
        authority.rights_epoch, authority.correction_generation, ())


def schema_source_handle(schema: FrameSchema) -> str:
    if type(schema) is not FrameSchema:
        _fail("FRAME_SCHEMA_REQUIRED")
    return f"source:motif-schema:{schema.identity}"


def schema_evidence_digest(schema: FrameSchema) -> str:
    if type(schema) is not FrameSchema:
        _fail("FRAME_SCHEMA_REQUIRED")
    return hashlib.sha256(schema.canonical_bytes()).hexdigest()


def _decision(authority, source_adapter_id, schema_id, revision):
    family = source_family_for_adapter(source_adapter_id)
    schema, _witness = lookup_source_pinned_frame_schema(
        schema_id, revision, source_family=family,
        atlas_selection=authority.atlas_selection)
    evidence = schema_evidence_digest(schema)
    matches = tuple(
        entry for entry in _load_registry()["entries"]
        if (entry["family"], entry["schema_id"], entry["revision"])
        == (family, schema_id, revision)
    )
    if len(matches) != 1 or matches[0]["evidence_sha256"] != evidence:
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_EVIDENCE_DRIFT", source_adapter_id)
    return schema, matches[0]


def current_source_schema_grant(
    authority: SourceSchemaRightsAuthority,
    source_adapter_id: str,
    schema_id: str,
    revision: int,
    *,
    task_scope: TaskScope,
    policy: ContextPolicy,
) -> SourceGrant:
    """Materialize one exact grant from current owner state, never caller state."""
    if type(authority) is not SourceSchemaRightsAuthority:
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_AUTHORITY_REQUIRED", source_adapter_id)
    authority.__post_init__()
    if (
        not isinstance(source_adapter_id, str) or not source_adapter_id
        or not isinstance(schema_id, str) or not schema_id
        or type(revision) is not int or revision < 1
        or type(task_scope) is not TaskScope
        or type(policy) is not ContextPolicy
        or task_scope.purpose is None
        or task_scope.semantic_release != authority.atlas_selection.release_sha256
        or policy.rights_epoch != authority.rights_epoch
        or task_scope.purpose not in policy.allowed_purposes
        or PUBLIC_FORMAL not in policy.allowed_regimes
        or task_scope.jurisdiction not in policy.allowed_jurisdictions
        or task_scope.scope not in policy.allowed_scopes
    ):
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_SCOPE_INVALID", source_adapter_id)
    schema, decision = _decision(
        authority, source_adapter_id, schema_id, revision)
    return SourceGrant(
        schema_source_handle(schema), task_scope.principal_id, task_scope.tenant_id,
        PUBLIC_FORMAL, task_scope.semantic_release, schema_evidence_digest(schema),
        (task_scope.purpose,), (task_scope.jurisdiction,), (task_scope.scope,),
        authority.rights_epoch, authority.correction_generation,
        PUBLIC_FORMAL_TIMELESS_EPOCH, PUBLIC_FORMAL_TIMELESS_EPOCH,
        revoked=decision["revoked"],
    )


def source_schema_rights_identity(authority: SourceSchemaRightsAuthority) -> dict:
    if type(authority) is not SourceSchemaRightsAuthority:
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_AUTHORITY_REQUIRED")
    authority.__post_init__()
    return {
        "atlas_bundle_id": authority.atlas_selection.bundle_id,
        "semantic_release": authority.atlas_selection.release_sha256,
        "source_bundle_id": authority.atlas_selection.source_bundle_id,
        "rights_epoch": authority.rights_epoch,
        "correction_generation": authority.correction_generation,
        "registry_sha256": authority.registry_sha256,
        "schema": IDENTITY_SCHEMA,
    }


def validate_source_schema_rights_identity(
    value: dict,
    atlas_selection: AtlasArtifactSelection,
) -> SourceSchemaRightsAuthority:
    authority = issue_source_schema_rights_authority(atlas_selection)
    if type(value) is not dict or value != source_schema_rights_identity(authority):
        _fail("BAMF_CONTEXT_SCHEMA_RIGHTS_IDENTITY_INVALID")
    return authority


__all__ = (
    "SourceSchemaRightsAuthority", "current_source_schema_grant",
    "issue_source_schema_rights_authority", "schema_evidence_digest",
    "schema_source_handle", "source_schema_rights_frontier",
    "source_schema_rights_identity", "validate_source_schema_rights_identity",
)
