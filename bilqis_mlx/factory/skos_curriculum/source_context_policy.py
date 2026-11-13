"""Policy-owner-issued finite temporal authority for A13 source contexts."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path

from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextPolicy, SourceFrontier, TaskScope,
)

from .common import _fail


SOURCE_CONTEXT_TRANSITION_AUTHORITY_SCHEMA = (
    "bilqis.source-context-transition-authority/v2"
)
SOURCE_CONTEXT_TEMPORAL_IDENTITY_SCHEMA = (
    "bilqis.source-context-temporal-identity/v1"
)
_POLICY_REGISTRY_SCHEMA = "bilqis.source-context-transition-policy-registry/v2"
_POLICY_REGISTRY = Path(__file__).with_name(
    "source_context_transition_policy_v2.json"
)
_POLICY_REGISTRY_SHA256 = (
    "4e68df20e78c573b24ee909abe95bfe62c8c23d18e3888507083dfe2e249a4a8"
)
_ISSUER = object()


def _contracts(entry: dict) -> tuple[TaskScope, ContextPolicy, SourceFrontier]:
    task = TaskScope(
        entry["principal_id"],
        entry["tenant_id"],
        entry["purpose"],
        entry["semantic_release"],
        entry["jurisdiction"],
        entry["scope"],
        entry["observed_frontier"],
        entry["current_effective_time"],
        entry["causal_prefix_end"],
    )
    policy = ContextPolicy(
        entry["policy_id"],
        entry["policy_epoch"],
        entry["rights_epoch"],
        (entry["purpose"],),
        (PUBLIC_FORMAL,),
        (entry["jurisdiction"],),
        (entry["scope"],),
        (PUBLIC_FORMAL,),
        ((PUBLIC_FORMAL, PUBLIC_FORMAL),),
        (),
    )
    frontier = SourceFrontier(
        entry["rights_epoch"], entry["correction_generation"], ()
    )
    return task, policy, frontier


@dataclass(frozen=True, init=False)
class SourceContextTransitionAuthority:
    """Opaque policy-owner authority for one finite A01 context transition."""

    atlas_bundle_id: str
    semantic_release: str
    source_bundle_id: str
    task: TaskScope
    policy: ContextPolicy
    frontier: SourceFrontier
    effective_from: int
    effective_until: int
    source_time: int
    effective_time: int
    observed_at: int
    recorded_at: int
    authority_registry_sha256: str
    schema: str = SOURCE_CONTEXT_TRANSITION_AUTHORITY_SCHEMA
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _fail("BAMF_SOURCE_CONTEXT_TRANSITION_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self) -> None:
        entry = _load_policy_registry()["entries"][0]
        expected_task, expected_policy, expected_frontier = _contracts(entry)
        if (
            getattr(self, "_issuance", None) is not _ISSUER
            or self.atlas_bundle_id != entry["atlas_bundle_id"]
            or self.semantic_release != entry["semantic_release"]
            or self.source_bundle_id != entry["source_bundle_id"]
            or self.task != expected_task
            or self.policy != expected_policy
            or self.frontier != expected_frontier
            or self.effective_from != entry["effective_from"]
            or self.effective_until != entry["effective_until"]
            or self.source_time != entry["source_time"]
            or self.effective_time != entry["effective_time"]
            or self.observed_at != entry["observed_at"]
            or self.recorded_at != entry["recorded_at"]
            or self.effective_time != self.effective_until
            or self.observed_at != self.task.observed_frontier
            or not self.source_time <= self.observed_at <= self.recorded_at
            or self.authority_registry_sha256 != _POLICY_REGISTRY_SHA256
            or self.schema != SOURCE_CONTEXT_TRANSITION_AUTHORITY_SCHEMA
        ):
            _fail("BAMF_SOURCE_CONTEXT_TRANSITION_AUTHORITY_INVALID")


def _load_policy_registry() -> dict:
    if _POLICY_REGISTRY.is_symlink() or not _POLICY_REGISTRY.is_file():
        _fail("BAMF_SOURCE_CONTEXT_TRANSITION_REGISTRY_MISSING")
    try:
        payload = _POLICY_REGISTRY.read_bytes()
        value = json.loads(payload)
    except (OSError, ValueError, UnicodeError):
        _fail("BAMF_SOURCE_CONTEXT_TRANSITION_REGISTRY_INVALID")
    expected_keys = {
        "atlas_bundle_id", "causal_prefix_end", "correction_generation",
        "current_effective_time", "effective_from", "effective_until",
        "effective_time", "jurisdiction", "observed_at", "observed_frontier",
        "policy_epoch", "policy_id", "recorded_at",
        "principal_id", "purpose", "rights_epoch", "scope",
        "semantic_release", "source_bundle_id", "source_time", "tenant_id",
    }
    if (
        hashlib.sha256(payload).hexdigest() != _POLICY_REGISTRY_SHA256
        or not isinstance(value, dict)
        or set(value) != {"schema", "entries"}
        or value["schema"] != _POLICY_REGISTRY_SCHEMA
        or not isinstance(value["entries"], list)
        or len(value["entries"]) != 1
        or not isinstance(value["entries"][0], dict)
        or set(value["entries"][0]) != expected_keys
        or any(
            type(value["entries"][0][name]) is not str
            or not value["entries"][0][name]
            for name in (
                "atlas_bundle_id", "jurisdiction", "policy_id",
                "principal_id", "purpose", "scope", "semantic_release",
                "source_bundle_id", "tenant_id",
            )
        )
        or any(
            type(value["entries"][0][name]) is not int
            or value["entries"][0][name] < 0
            for name in (
                "causal_prefix_end", "correction_generation",
                "current_effective_time", "effective_from", "effective_until",
                "effective_time", "observed_at", "observed_frontier",
                "policy_epoch", "recorded_at", "rights_epoch", "source_time",
            )
        )
        or value["entries"][0]["effective_time"]
           != value["entries"][0]["effective_until"]
        or value["entries"][0]["observed_at"]
           != value["entries"][0]["observed_frontier"]
        or not (
            value["entries"][0]["source_time"]
            <= value["entries"][0]["observed_at"]
            <= value["entries"][0]["recorded_at"]
        )
    ):
        _fail("BAMF_SOURCE_CONTEXT_TRANSITION_REGISTRY_INVALID")
    return value


def issue_source_context_transition_authority(
    atlas: AtlasArtifactSelection,
) -> SourceContextTransitionAuthority:
    """Issue the one repository-governed temporal transition for the pinned A01 source.

    Callers supply only the source selection. Policy identity, current logical time,
    validity bounds, observation frontier, rights/correction epochs, and actor scope
    are read from the hash-pinned policy registry.
    """
    if type(atlas) is not AtlasArtifactSelection:
        _fail("BAMF_SOURCE_CONTEXT_TRANSITION_SOURCE_REQUIRED")
    AtlasArtifactSelection.__post_init__(atlas)
    entry = _load_policy_registry()["entries"][0]
    expected = (
        entry.get("atlas_bundle_id"),
        entry.get("semantic_release"),
        entry.get("source_bundle_id"),
    )
    if expected != (atlas.bundle_id, atlas.release_sha256, atlas.source_bundle_id):
        _fail("BAMF_SOURCE_CONTEXT_TRANSITION_SOURCE_NOT_AUTHORIZED")

    task, policy, frontier = _contracts(entry)
    authority = object.__new__(SourceContextTransitionAuthority)
    for name, value in (
        ("atlas_bundle_id", entry["atlas_bundle_id"]),
        ("semantic_release", entry["semantic_release"]),
        ("source_bundle_id", entry["source_bundle_id"]),
        ("task", task),
        ("policy", policy),
        ("frontier", frontier),
        ("effective_from", entry["effective_from"]),
        ("effective_until", entry["effective_until"]),
        ("source_time", entry["source_time"]),
        ("effective_time", entry["effective_time"]),
        ("observed_at", entry["observed_at"]),
        ("recorded_at", entry["recorded_at"]),
        ("authority_registry_sha256", _POLICY_REGISTRY_SHA256),
        ("schema", SOURCE_CONTEXT_TRANSITION_AUTHORITY_SCHEMA),
        ("_issuance", _ISSUER),
    ):
        object.__setattr__(authority, name, value)
    authority.__post_init__()
    return authority


def _temporal_identity_from_entry(entry: dict) -> dict:
    return {
        "source_time": entry["source_time"],
        "effective_time": entry["effective_time"],
        "observed_at": entry["observed_at"],
        "recorded_at": entry["recorded_at"],
        "authority_registry_sha256": _POLICY_REGISTRY_SHA256,
        "schema_version": SOURCE_CONTEXT_TEMPORAL_IDENTITY_SCHEMA,
    }


def source_context_temporal_identity(
    authority: SourceContextTransitionAuthority,
) -> dict:
    """Project the exact source-owned temporal tuple without granting authority."""
    if type(authority) is not SourceContextTransitionAuthority:
        _fail("BAMF_SOURCE_CONTEXT_TEMPORAL_AUTHORITY_REQUIRED")
    authority.__post_init__()
    value = {
        "source_time": authority.source_time,
        "effective_time": authority.effective_time,
        "observed_at": authority.observed_at,
        "recorded_at": authority.recorded_at,
        "authority_registry_sha256": authority.authority_registry_sha256,
        "schema_version": SOURCE_CONTEXT_TEMPORAL_IDENTITY_SCHEMA,
    }
    return validate_source_context_temporal_identity(value)


def validate_source_context_temporal_identity(value: dict) -> dict:
    """Revalidate a persisted tuple against the hash-pinned source policy."""
    expected = _temporal_identity_from_entry(_load_policy_registry()["entries"][0])
    if type(value) is not dict or value != expected:
        _fail("BAMF_SOURCE_CONTEXT_TEMPORAL_IDENTITY_INVALID")
    return dict(value)


__all__ = (
    "SourceContextTransitionAuthority",
    "SOURCE_CONTEXT_TEMPORAL_IDENTITY_SCHEMA",
    "issue_source_context_transition_authority",
    "source_context_temporal_identity",
    "validate_source_context_temporal_identity",
)
