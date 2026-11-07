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
    "bilqis.source-context-transition-authority/v1"
)
_POLICY_REGISTRY_SCHEMA = "bilqis.source-context-transition-policy-registry/v1"
_POLICY_REGISTRY = Path(__file__).with_name(
    "source_context_transition_policy_v1.json"
)
_POLICY_REGISTRY_SHA256 = (
    "6ac59c878f5e1ce5f0fafca4710669626b3e357d60b4c5d02edaee29f31d1ea9"
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
        "jurisdiction", "observed_frontier", "policy_epoch", "policy_id",
        "principal_id", "purpose", "rights_epoch", "scope",
        "semantic_release", "source_bundle_id", "tenant_id",
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
                "observed_frontier", "policy_epoch", "rights_epoch",
            )
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
        ("authority_registry_sha256", _POLICY_REGISTRY_SHA256),
        ("schema", SOURCE_CONTEXT_TRANSITION_AUTHORITY_SCHEMA),
        ("_issuance", _ISSUER),
    ):
        object.__setattr__(authority, name, value)
    authority.__post_init__()
    return authority


__all__ = (
    "SourceContextTransitionAuthority",
    "issue_source_context_transition_authority",
)
