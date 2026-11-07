"""B13-issued retained cache authority consumed by the B11 forward owner."""
from __future__ import annotations

from dataclasses import dataclass, field
import secrets

from bilqis_mlx.data_plane import SHA256_HEX_LENGTH
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_engram import MotifManifest


_ISSUER = object()


def _invalid(reason: str) -> None:
    ErrorBus.Raise(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == SHA256_HEX_LENGTH
        and all(char in "0123456789abcdef" for char in value)
    )


@dataclass(frozen=True, init=False)
class AcceptedExecutionCache:
    """A motif manifest authenticated against one accepted B13 generation."""

    run_id: str
    generation: int
    accepted_manifest_sha256: str
    generation_binding: str
    motif_manifest: MotifManifest
    schema_version: str = "bilqis.mlx.b13-accepted-execution-cache/v1"
    _issuance: object = field(init=False, repr=False, compare=False)
    _motif_artifact_owner: object | None = field(init=False, repr=False, compare=False)
    _cache_mac_key: bytes = field(init=False, repr=False, compare=False)
    _cache_authority: object | None = field(init=False, repr=False, compare=False)
    _cache_authority_registry: object | None = field(init=False, repr=False, compare=False)
    _cache_eligibility_source: object | None = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid("B13_EXECUTION_CACHE_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self) -> None:
        if (
            getattr(self, "_issuance", None) is not _ISSUER
            or not isinstance(self.run_id, str) or not self.run_id
            or type(self.generation) is not int or self.generation < 0
            or not _digest(self.accepted_manifest_sha256)
            or not _digest(self.generation_binding)
            or type(self.motif_manifest) is not MotifManifest
            or self.schema_version
            != "bilqis.mlx.b13-accepted-execution-cache/v1"
        ):
            _invalid("B13_EXECUTION_CACHE_INVALID")


def _issue_accepted_execution_cache(
    *,
    run_id: str,
    generation: int,
    accepted_manifest_sha256: str,
    generation_binding: str,
    motif_manifest: MotifManifest,
) -> AcceptedExecutionCache:
    cache = object.__new__(AcceptedExecutionCache)
    for name, value in (
        ("run_id", run_id),
        ("generation", generation),
        ("accepted_manifest_sha256", accepted_manifest_sha256),
        ("generation_binding", generation_binding),
        ("motif_manifest", motif_manifest),
        ("schema_version", "bilqis.mlx.b13-accepted-execution-cache/v1"),
        ("_issuance", _ISSUER),
        ("_motif_artifact_owner", None),
        ("_cache_mac_key", secrets.token_bytes(32)),
        ("_cache_authority", None),
        ("_cache_authority_registry", None),
        ("_cache_eligibility_source", None),
    ):
        object.__setattr__(cache, name, value)
    cache.__post_init__()
    return cache


def require_accepted_execution_cache(cache) -> AcceptedExecutionCache:
    if type(cache) is not AcceptedExecutionCache:
        _invalid("B13_EXECUTION_CACHE_REQUIRED")
    cache.__post_init__()
    return cache


def bind_motif_artifact_owner(cache, compiled):
    """Bind mutable C09 hold state to one authenticated cache lifetime."""
    cache = require_accepted_execution_cache(cache)
    from bilqis_mlx.runtime.atlas_motif_owner import MotifArtifactOwner
    owner = cache._motif_artifact_owner
    if owner is None:
        owner = MotifArtifactOwner(cache, compiled)
        object.__setattr__(cache, "_motif_artifact_owner", owner)
    owner.require(cache, compiled)
    return owner


def bind_cache_authority(cache, registry, eligibility_source=None):
    """Bind one opaque B14 cache authority to authenticated B13 custody."""
    cache = require_accepted_execution_cache(cache)
    from bilqis_mlx.runtime.atlas_cache_runtime import (
        _ACCEPTED_CACHE_AUTHORITY_ISSUER,
    )
    authority = cache._cache_authority
    if authority is None:
        authority = _ACCEPTED_CACHE_AUTHORITY_ISSUER.issue(
            cache, registry, eligibility_source)
        object.__setattr__(cache, "_cache_authority", authority)
        object.__setattr__(cache, "_cache_authority_registry", registry)
        object.__setattr__(cache, "_cache_eligibility_source", eligibility_source)
        return authority
    if (registry != cache._cache_authority_registry
            or eligibility_source is not cache._cache_eligibility_source):
        _invalid("B13_CACHE_AUTHORITY_SOURCE_DRIFT")
    return authority


__all__ = (
    "AcceptedExecutionCache", "bind_cache_authority", "bind_motif_artifact_owner",
    "require_accepted_execution_cache",
)
