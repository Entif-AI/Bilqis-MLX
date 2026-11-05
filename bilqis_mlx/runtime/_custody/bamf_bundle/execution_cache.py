"""B13-issued retained cache authority consumed by the B11 forward owner."""
from __future__ import annotations

from dataclasses import dataclass, field

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
    ):
        object.__setattr__(cache, name, value)
    cache.__post_init__()
    return cache


def require_accepted_execution_cache(cache) -> AcceptedExecutionCache:
    if type(cache) is not AcceptedExecutionCache:
        _invalid("B13_EXECUTION_CACHE_REQUIRED")
    cache.__post_init__()
    return cache


__all__ = ("AcceptedExecutionCache", "require_accepted_execution_cache")
